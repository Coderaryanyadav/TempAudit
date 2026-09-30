import unittest
import os
import io
import json
import time
import pandas as pd
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db_connection, init_db
from backend.app.auth import create_access_token
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

class TestFinancialDataImportModule(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        init_db()
        self.run_id = str(int(time.time()))[-4:]
        
        self.auditor_token = create_access_token(data={"sub": "admin", "role": "Admin", "id": 1})
        self.admin_token = create_access_token(data={"sub": "admin", "role": "Admin", "id": 1})

        # Ensure sample engagement exists
        conn = get_db_connection()
        eng = conn.execute("SELECT id FROM engagements ORDER BY id ASC LIMIT 1").fetchone()
        if not eng:
            cursor = conn.execute("""
            INSERT INTO clients (name, entity_type, created_at, updated_at)
            VALUES ('Import Test Client', 'Private Limited Company', datetime('now'), datetime('now'))
            """)
            c_id = cursor.lastrowid
            cursor2 = conn.execute("""
            INSERT INTO engagements (client_id, title, audit_type, financial_year, created_at, updated_at)
            VALUES (?, 'Import Test Audit', 'Statutory Audit', '2024-25', datetime('now'), datetime('now'))
            """, (c_id,))
            self.engagement_id = cursor2.lastrowid
        else:
            self.engagement_id = eng["id"]
        conn.close()

    def test_01_upload_and_preview_csv(self):
        """Test uploading CSV file, column detection, and auto-mapping suggestion."""
        csv_content = """Date,Voucher No,Invoice No,Ledger,Party Name,GSTIN,Debit,Credit,Narration
01-04-2024,VCH-001,INV-1001,Sales Account,Sharma Traders,27AAAFE1234G1Z8,0.00,50000.00,Sale of industrial valves
02-04-2024,VCH-002,INV-1002,Purchase Account,Apex Steel Ltd,27AABCP1234F1Z5,25000.00,0.00,Raw material purchase
03-04-2024,VCH-003,INV-1003,Office Rent,Landlord Property,,15000.00,0.00,April rent payment
"""
        csv_file = io.BytesIO(csv_content.encode("utf-8"))

        res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "General Ledger"},
            files={"file": ("sample_gl.csv", csv_file, "text/csv")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("file_id", data)
        self.assertEqual(data["file_name"], "sample_gl.csv")
        self.assertIn("columns", data)
        self.assertIn("suggested_mapping", data)
        self.assertIn("preview_rows", data)
        self.assertEqual(len(data["preview_rows"]), 3)
        self.assertEqual(data["suggested_mapping"].get("Date"), "date")
        self.assertEqual(data["suggested_mapping"].get("Debit"), "debit")
        self.assertEqual(data["suggested_mapping"].get("Credit"), "credit")

    def test_02_upload_and_preview_excel(self):
        """Test uploading Excel (.xlsx) file with multi-column auto-mapping."""
        df = pd.DataFrame([
            {"Date": "2024-04-10", "Vch_No": "BK-01", "Particulars": "HDFC Bank", "Debit Amount": 100000.0, "Credit Amount": 0.0, "Remarks": "Customer Collection"},
            {"Date": "2024-04-12", "Vch_No": "BK-02", "Particulars": "Electricity Exp", "Debit Amount": 0.0, "Credit Amount": 4500.0, "Remarks": "Bill Payment"}
        ])
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "Bank Statement"},
            files={"file": ("bank_statement.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file_type"], ".xlsx")
        self.assertEqual(data["estimated_rows"], 2)

    def test_03_upload_and_preview_json(self):
        """Test uploading JSON transaction dataset."""
        json_data = [
            {"date": "2024-05-01", "voucher_no": "JV-01", "ledger": "Depreciation", "debit": 12000.0, "credit": 0.0, "description": "Depreciation entry"},
            {"date": "2024-05-01", "voucher_no": "JV-02", "ledger": "Accumulated Dep", "debit": 0.0, "credit": 12000.0, "description": "Depreciation provision"}
        ]
        json_file = io.BytesIO(json.dumps(json_data).encode("utf-8"))

        res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "Journal Entries"},
            files={"file": ("journal_data.json", json_file, "application/json")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file_type"], ".json")
        self.assertEqual(len(data["preview_rows"]), 2)

    def test_04_upload_and_preview_pdf(self):
        """Test uploading PDF bank statement and extracting tabular text."""
        pdf_buffer = io.BytesIO()
        p = canvas.Canvas(pdf_buffer, pagesize=letter)
        p.drawString(50, 750, "Bank Account Statement - HDFC Bank")
        p.drawString(50, 720, "Date        Particulars          Chq_No    Debit       Credit      Balance")
        p.drawString(50, 700, "01-04-2024  NEFT INFLOW CLIENT   10012     0.00        50000.00    150000.00")
        p.drawString(50, 680, "05-04-2024  OFFICE ELECTRICITY   99281     4200.00     0.00        145800.00")
        p.save()
        pdf_buffer.seek(0)

        res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "Bank Statement"},
            files={"file": ("hdfc_statement.pdf", pdf_buffer, "application/pdf")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file_type"], ".pdf")
        self.assertTrue(len(data["preview_rows"]) > 0)

    def test_05_pre_import_validation_detects_anomalies(self):
        """Test pre-import validation for invalid dates, non-numeric values, GSTIN format, and duplicate rows."""
        dirty_csv = """Date,Voucher,Invoice,Ledger,Debit,Credit,GSTIN
99-99-9999,VCH-01,INV-1,Legal Fees,5000,0,INVALID_GST
01-04-2024,VCH-02,INV-2,Travel Expense,TEN THOUSAND,0,27AAAFE1234G1Z8
02-04-2024,VCH-03,INV-3,Consulting,4000,2000,27AAAFE1234G1Z8
03-04-2024,VCH-04,INV-4,Audit Fees,25000,0,27AAAFE1234G1Z8
03-04-2024,VCH-04,INV-4,Audit Fees,25000,0,27AAAFE1234G1Z8
"""
        csv_file = io.BytesIO(dirty_csv.encode("utf-8"))
        up_res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "Sales Register"},
            files={"file": ("dirty_data.csv", csv_file, "text/csv")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        ).json()
        file_id = up_res["file_id"]

        mapping = {
            "Date": "date",
            "Voucher": "voucher_no",
            "Invoice": "invoice_no",
            "Ledger": "ledger",
            "Debit": "debit",
            "Credit": "credit",
            "GSTIN": "gstin"
        }

        val_res = self.client.post(
            "/api/import/validate",
            json={"file_id": file_id, "column_mapping": mapping, "data_category": "Sales Register"},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(val_res.status_code, 200)
        report = val_res.json()["validation_report"]
        summary = report["error_summary"]

        self.assertTrue(summary["invalid_dates"] >= 1)
        self.assertTrue(summary["invalid_numeric"] >= 1)
        self.assertTrue(summary["invalid_gstin"] >= 1)
        self.assertTrue(summary["debit_credit_conflicts"] >= 1)
        self.assertTrue(summary["duplicate_rows"] >= 1)

    def test_06_apply_mapping_and_download_error_report(self):
        """Test applying mapping, persisting transactions with original values, and downloading CSV error report."""
        csv_content = """Date,Voucher No,Account Head,Party,Amount,Debit,Credit,Tax,GSTIN,Narration
01-04-2024,V-101,Sales,Global Retailers,118000,0,100000,18000,27AAAFE1234G1Z8,Q1 Bulk supply
02-04-2024,V-102,Freight Outward,Express Cargo,5000,5000,0,0,,Transport charges
"""
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        up_res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "Sales Register"},
            files={"file": ("sales_register.csv", csv_file, "text/csv")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        ).json()
        file_id = up_res["file_id"]

        mapping = {
            "Date": "date",
            "Voucher No": "voucher_no",
            "Account Head": "ledger",
            "Party": "party_name",
            "Amount": "amount",
            "Debit": "debit",
            "Credit": "credit",
            "Tax": "tax_amount",
            "GSTIN": "gstin",
            "Narration": "description"
        }

        # Apply mapping
        import_res = self.client.post(
            "/api/import/apply-mapping",
            json={"file_id": file_id, "column_mapping": mapping, "data_category": "Sales Register"},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(import_res.status_code, 200)
        res_data = import_res.json()
        self.assertEqual(res_data["imported_rows"], 2)

        # Verify database record and original values preservation
        conn = get_db_connection()
        tx = conn.execute("SELECT * FROM transactions WHERE file_id = ? ORDER BY id ASC LIMIT 1", (file_id,)).fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(tx["voucher_no"], "V-101")
        self.assertEqual(tx["party_name"], "Global Retailers")
        self.assertIsNotNone(tx["original_row_json"])
        orig_obj = json.loads(tx["original_row_json"])
        self.assertEqual(orig_obj["Party"], "Global Retailers")
        conn.close()

        # Download error report
        err_res = self.client.get(
            f"/api/import/errors/{file_id}/download",
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )
        self.assertEqual(err_res.status_code, 200)
        self.assertIn("text/csv", err_res.headers["content-type"])
        self.assertIn("Row Number", err_res.text)

    def test_07_delete_uploaded_file_and_cleanup(self):
        """Test deleting an uploaded dataset cleanly deletes associated transactions."""
        csv_content = """Date,Ledger,Debit,Credit\n01-04-2024,Temp Exp,100,0\n"""
        up_res = self.client.post(
            "/api/import/upload",
            data={"engagement_id": self.engagement_id, "data_category": "General Ledger"},
            files={"file": ("to_delete.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        ).json()
        file_id = up_res["file_id"]

        self.client.post(
            "/api/import/apply-mapping",
            json={"file_id": file_id, "column_mapping": {"Date": "date", "Ledger": "ledger", "Debit": "debit"}},
            headers={"Authorization": f"Bearer {self.auditor_token}"}
        )

        del_res = self.client.delete(
            f"/api/import/files/{file_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(del_res.status_code, 200)

        conn = get_db_connection()
        remaining_tx = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE file_id = ?", (file_id,)).fetchone()["c"]
        self.assertEqual(remaining_tx, 0)
        conn.close()

if __name__ == "__main__":
    unittest.main()
