"""
Deep Bank Reconciliation Engine Verification (Phase 6)
Verifies synthetic reconciliation matching passes, unpresented cheques,
outstanding deposits, direct bank charges, and BRS roll-forward arithmetic.
"""
import pytest
from datetime import datetime
from backend.app.database import get_db_connection
from backend.app.services.bank_reconciliation_engine import run_bank_reconciliation

def test_bank_reconciliation_exact_and_clearance_matching():
    """Phase 6: Verifies exact matching (Pass 1) and clearance delay matching (Pass 2)."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, created_at) VALUES ('Recon Corp', 'ABCDE2222B', ?)", (now_str,))
    client_id = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Recon Engagement', '2024-25', ?)", (client_id, now_str))
    eng_id = cur.lastrowid

    # 1. Book transactions (Cash Book / Bank Ledger)
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, '2024-05-01', 'CHQ-1001', 'HDFC Bank Account', 'Vendor Alpha', 0.0, 50000.0, 50000.0, 'Payment')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, '2024-05-05', 'CHQ-1002', 'HDFC Bank Account', 'Vendor Beta', 0.0, 75000.0, 75000.0, 'Payment')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, '2024-05-10', 'DEP-2001', 'HDFC Bank Account', 'Customer Gamma', 120000.0, 0.0, 120000.0, 'Receipt')
    """, (eng_id,))

    # 2. Bank statement transactions (File B)
    cur_f = conn.execute("""
        INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, uploaded_at)
        VALUES (?, 'bank_statement.csv', 'CSV', '/tmp/bank.csv', 'Bank Statement', ?)
    """, (eng_id, now_str))
    file_b_id = cur_f.lastrowid

    # Statement: Item 1 cleared exact date & cheque
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, ?, '2024-05-01', 'CHQ-1001', 'Bank Statement', 'Vendor Alpha', 50000.0, 0.0, 50000.0, 'Withdrawal')
    """, (eng_id, file_b_id))
    # Statement: Item 2 cleared 3 days later (clearance delay)
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, ?, '2024-05-08', 'REF-9988', 'Bank Statement', 'Vendor Beta', 75000.0, 0.0, 75000.0, 'Withdrawal')
    """, (eng_id, file_b_id))
    # Statement: Item 3 cleared exact amount
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, ?, '2024-05-11', 'DEP-2001', 'Bank Statement', 'Customer Gamma', 0.0, 120000.0, 120000.0, 'Deposit')
    """, (eng_id, file_b_id))
    conn.commit()
    conn.close()

    res = run_bank_reconciliation(
        engagement_id=eng_id,
        bank_ledger_name="HDFC Bank Account",
        file_b_id=file_b_id,
        title="May 2024 HDFC BRS"
    )

    assert res["summary"]["matched_count"] == 3
    assert res["summary"]["unmatched_bank_count"] == 0
    assert res["summary"]["unmatched_book_count"] == 0
    assert res["summary"]["net_unreconciled_difference"] == 0.0

def test_bank_reconciliation_timing_exceptions_and_charges():
    """Phase 6: Verifies unpresented cheques, outstanding deposits, bank charges, and BRS arithmetic."""
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cur = conn.execute("INSERT INTO clients (name, pan, created_at) VALUES ('Timing Exceptions Corp', 'ABCDE3333C', ?)", (now_str,))
    client_id = cur.lastrowid
    cur = conn.execute("INSERT INTO engagements (client_id, title, financial_year, created_at) VALUES (?, 'Timing BRS Eng', '2024-25', ?)", (client_id, now_str))
    eng_id = cur.lastrowid

    # 1. Books: ₹1,00,000 opening deposit, ₹25,000 unpresented cheque, ₹15,000 outstanding deposit
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, '2024-03-10', 'DEP-01', 'SBI Current Account', 'Client Opening', 100000.0, 0.0, 100000.0, 'Receipt')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, '2024-03-28', 'CHQ-555', 'SBI Current Account', 'Late Vendor', 0.0, 25000.0, 25000.0, 'Payment', 'Cheque issued to supplier')
    """, (eng_id,))
    conn.execute("""
        INSERT INTO transactions (engagement_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, '2024-03-31', 'RCPT-888', 'SBI Current Account', 'Outstation Customer', 15000.0, 0.0, 15000.0, 'Receipt', 'Cheque deposited in drop box')
    """, (eng_id,))

    # 2. Bank Statement:
    cur_f = conn.execute("""
        INSERT INTO uploaded_files (engagement_id, file_name, file_type, file_path, data_category, uploaded_at)
        VALUES (?, 'sbi_statement.csv', 'CSV', '/tmp/sbi.csv', 'Bank Statement', ?)
    """, (eng_id, now_str))
    file_b_id = cur_f.lastrowid

    # Cleared opening deposit
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type)
        VALUES (?, ?, '2024-03-10', 'DEP-01', 'Bank Statement', 'Client Opening', 0.0, 100000.0, 100000.0, 'Deposit')
    """, (eng_id, file_b_id))
    # Unrecorded Bank Charge: ₹1,180 (SMS/Folio charges + GST)
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, ?, '2024-03-31', 'TXN-BANK-01', 'Bank Statement', 'SBI Branch', 1180.0, 0.0, 1180.0, 'Debit', 'Annual folio maintenance charge and SMS fee')
    """, (eng_id, file_b_id))
    # Unrecorded Interest Credit: ₹3,500
    conn.execute("""
        INSERT INTO transactions (engagement_id, file_id, date, voucher_no, ledger, party_name, debit, credit, amount, transaction_type, description)
        VALUES (?, ?, '2024-03-31', 'TXN-BANK-02', 'Bank Statement', 'SBI Interest', 0.0, 3500.0, 3500.0, 'Credit', 'Half yearly savings interest credit')
    """, (eng_id, file_b_id))
    conn.commit()
    conn.close()

    res = run_bank_reconciliation(
        engagement_id=eng_id,
        bank_ledger_name="SBI Current Account",
        file_b_id=file_b_id,
        title="March 2024 SBI BRS"
    )

    recon_id = res["recon_id"]
    summary = res["summary"]

    assert summary["matched_count"] == 1
    assert summary["unpresented_cheques_amount"] == 25000.0
    assert summary["outstanding_deposits_amount"] == 15000.0
    assert summary["bank_charges_amount"] == 1180.0
    assert summary["interest_credited_amount"] == 3500.0

    # Verify persisted items in reconciliation_items
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM reconciliation_items WHERE recon_id = ?", (recon_id,)).fetchall()
    conn.close()

    types = [it["item_type"] for it in items]
    assert "UNPRESENTED_CHEQUE" in types
    assert "OUTSTANDING_DEPOSIT" in types
    assert "BANK_CHARGES" in types
    assert "INTEREST_CREDIT" in types

    # Verify schema fields populated
    unpresented_item = next(it for it in items if it["item_type"] == "UNPRESENTED_CHEQUE")
    assert unpresented_item["amount_a"] == 25000.0
    assert unpresented_item["status"] == "Unmatched"
    assert unpresented_item["match_level"] == "UNMATCHED"
