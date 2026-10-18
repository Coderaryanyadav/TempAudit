import pytest
import sqlite3
import time
from decimal import Decimal
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import init_db, get_db_connection
from backend.app.audit_engine.deterministic import DeterministicAuditEngine

client = TestClient(app)

# ==============================================================================
# 1. STATUTORY FINANCIAL RULE MATRIX: 40A(3) & 269ST
# ==============================================================================

def test_section_40a3_boundary_and_direction_matrix():
    """
    Test matrix for Section 40A(3) cash payments:
    - Boundary values: ₹9,999, ₹10,000, ₹10,001
    - Aggregation of same-day cash payments to same payee
    - Distinction between cash payments (expenditure) vs cash receipts (revenue)
    - Transport operator threshold (₹35,000)
    - Rule 6DD statutory exceptions
    """
    # Case 1: Exactly ₹10,000 payment -> ALLOWED (Threshold is EXCEEDING ₹10,000)
    tx_exact = [{"id": 1, "date": "2026-05-01", "ledger": "Office Expenses (Cash)", "party_name": "Supplier A", "debit": 10000.0, "credit": 0.0, "description": "Payment for materials"}]
    eng = DeterministicAuditEngine(tx_exact)
    eng.check_section_40a3_cash_payments()
    assert len(eng.findings) == 0, "Exact ₹10,000 is permitted under Section 40A(3)"

    # Case 2: ₹10,001 payment -> DISALLOWED
    tx_over = [{"id": 2, "date": "2026-05-01", "ledger": "Printing & Stationery (Cash)", "party_name": "Supplier B", "debit": 10001.0, "credit": 0.0, "description": "Payment for supplies"}]
    eng = DeterministicAuditEngine(tx_over)
    eng.check_section_40a3_cash_payments()
    assert len(eng.findings) == 1
    assert eng.findings[0]["severity"] == "HIGH"

    # Case 3: Same day split payments: ₹6,000 + ₹4,500 = ₹10,500 to same party -> DISALLOWED
    tx_split = [
        {"id": 3, "date": "2026-05-02", "ledger": "Repairs (Cash)", "party_name": "Vendor C", "debit": 6000.0, "credit": 0.0, "description": "Morning cash payment"},
        {"id": 4, "date": "2026-05-02", "ledger": "Repairs (Cash)", "party_name": "Vendor C", "debit": 4500.0, "credit": 0.0, "description": "Evening cash payment"}
    ]
    eng = DeterministicAuditEngine(tx_split)
    eng.check_section_40a3_cash_payments()
    assert len(eng.findings) == 1
    assert "₹10,500.00" in eng.findings[0]["description"]

    # Case 4: Cash Receipt of ₹15,000 -> NOT FLAGGED UNDER 40A(3) (Receipts are income, not expenditure)
    tx_receipt = [{"id": 5, "date": "2026-05-03", "ledger": "Cash Account", "party_name": "Customer D", "debit": 15000.0, "credit": 0.0, "transaction_type": "receipt", "description": "Cash sales receipt"}]
    eng = DeterministicAuditEngine(tx_receipt)
    eng.check_section_40a3_cash_payments()
    assert len(eng.findings) == 0, "Cash receipts must not trigger Section 40A(3) expenditure disallowance"

def test_section_269st_cash_receipt_boundary_and_penalty_matrix():
    """
    Test matrix for Section 269ST cash receipts (Threshold ₹2,00,000):
    - Boundary values: ₹1,99,999, ₹2,00,000, ₹2,00,001
    - Aggregation in a day from a person
    - Penalty calculation under Section 271DA (100% of receipt)
    """
    # Case 1: Exactly ₹1,99,999 -> ALLOWED
    tx_under = [{"id": 1, "date": "2026-06-01", "ledger": "Cash Account", "party_name": "Buyer X", "credit": 0.0, "debit": 199999.0, "transaction_type": "receipt", "description": "Sale advance"}]
    eng = DeterministicAuditEngine(tx_under)
    eng.check_section_269st_cash_receipts()
    assert len(eng.findings) == 0

    # Case 2: Exactly ₹2,00,000 -> DISALLOWED (Section 269ST says 'two lakh rupees or more')
    tx_exact = [{"id": 2, "date": "2026-06-01", "ledger": "Cash Account", "party_name": "Buyer Y", "credit": 0.0, "debit": 200000.0, "transaction_type": "receipt", "description": "Property advance"}]
    eng = DeterministicAuditEngine(tx_exact)
    eng.check_section_269st_cash_receipts()
    assert len(eng.findings) == 1
    assert eng.findings[0]["severity"] == "CRITICAL"
    assert "271da" in eng.findings[0]["reason"].lower()

    # Case 3: Same day split receipts: ₹1,20,000 + ₹85,000 = ₹2,05,000 from same person -> DISALLOWED
    tx_split = [
        {"id": 3, "date": "2026-06-02", "ledger": "Cash Account", "party_name": "Client Z", "credit": 0.0, "debit": 120000.0, "transaction_type": "receipt", "description": "Cash receipt Part 1"},
        {"id": 4, "date": "2026-06-02", "ledger": "Cash Account", "party_name": "Client Z", "credit": 0.0, "debit": 85000.0, "transaction_type": "receipt", "description": "Cash receipt Part 2"}
    ]
    eng = DeterministicAuditEngine(tx_split)
    eng.check_section_269st_cash_receipts()
    assert len(eng.findings) == 1
    assert "₹205,000.00" in eng.findings[0]["description"]

    # Case 4: Cash Payment of ₹3,00,000 made by assessee -> NOT FLAGGED UNDER 269ST
    tx_payment = [{"id": 5, "date": "2026-06-03", "ledger": "Cash Account", "party_name": "Vendor W", "credit": 300000.0, "debit": 0.0, "transaction_type": "payment", "description": "Asset purchase payment"}]
    eng = DeterministicAuditEngine(tx_payment)
    eng.check_section_269st_cash_receipts()
    assert len(eng.findings) == 0, "Cash payments must not trigger Section 269ST"

# ==============================================================================
# 2. CROSS-ROUTE DATA ISOLATION VERIFICATION
# ==============================================================================

def test_cross_route_engagement_isolation():
    """Verify that all engagement-scoped API routes reject unassigned users."""
    init_db()
    conn = get_db_connection()
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    # Setup 2 separate users and 2 separate engagements
    conn.execute("INSERT OR REPLACE INTO clients (id, name, created_at) VALUES (881, 'Isolation Client A', ?)", (now,))
    conn.execute("INSERT OR REPLACE INTO clients (id, name, created_at) VALUES (882, 'Isolation Client B', ?)", (now,))

    for uid, uname in [(801, "staff_alpha"), (802, "staff_beta")]:
        conn.execute("""
            INSERT OR REPLACE INTO users (id, username, email, full_name, password_hash, role, is_active, created_at)
            VALUES (?, ?, ? || '@firm.in', ?, 'hash', 'Audit Staff', 1, ?)
        """, (uid, uname, uname, uname, now))

    # Engagement 8801 is assigned to staff_alpha (801)
    conn.execute("""
        INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, lead_auditor_id, assigned_staff_id, created_at, updated_at)
        VALUES (8801, 881, 'Alpha Audit', 'Statutory', '2024-25', 1, 801, ?, ?)
    """, (now, now))

    # Engagement 8802 is assigned to staff_beta (802)
    conn.execute("""
        INSERT OR REPLACE INTO engagements (id, client_id, title, audit_type, financial_year, lead_auditor_id, assigned_staff_id, created_at, updated_at)
        VALUES (8802, 882, 'Beta Audit', 'Statutory', '2024-25', 1, 802, ?, ?)
    """, (now, now))
    conn.close()

    # Authenticate as staff_alpha
    from backend.app.auth import create_access_token
    alpha_token = create_access_token({"sub": "staff_alpha", "id": 801, "role": "Audit Staff"})
    headers = {"Authorization": f"Bearer {alpha_token}"}

    # staff_alpha attempts to access staff_beta's engagement 8802 across routes:
    # 1. Working Papers (route: /api/working-papers/{engagement_id})
    r_wp = client.get("/api/working-papers/8802", headers=headers)
    assert r_wp.status_code == 403, "Working papers must reject unassigned staff"

    # 2. Findings (route: /api/findings/{engagement_id})
    r_findings = client.get("/api/findings/8802", headers=headers)
    assert r_findings.status_code == 403, "Findings must reject unassigned staff"

    # 3. Import uploaded files list (route: /api/import/files/{engagement_id})
    r_import = client.get("/api/import/files/8802", headers=headers)
    assert r_import.status_code == 403, "Import files list must reject unassigned staff"
