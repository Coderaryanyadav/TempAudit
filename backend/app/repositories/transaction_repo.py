import sqlite3
from typing import List, Dict, Any, Optional
from decimal import Decimal
from backend.app.utils.money import to_decimal, quantize_money

class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_id(self, tx_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None

    def list_by_engagement(
        self,
        engagement_id: int,
        limit: int = 1000,
        offset: int = 0,
        ledger: Optional[str] = None,
        party_name: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM transactions WHERE engagement_id = ?"
        params: List[Any] = [engagement_id]

        if ledger:
            query += " AND ledger = ?"
            params.append(ledger)
        if party_name:
            query += " AND party_name LIKE ?"
            params.append(f"%{party_name}%")
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        query += " ORDER BY date ASC, id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def count_by_engagement(self, engagement_id: int) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchone()
        return row["cnt"] if row else 0

    def get_totals_by_engagement(self, engagement_id: int) -> Dict[str, Decimal]:
        rows = self.conn.execute(
            "SELECT debit, credit, amount, tax_amount FROM transactions WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchall()
        
        tot_debit = Decimal("0.00")
        tot_credit = Decimal("0.00")
        tot_tax = Decimal("0.00")
        
        for r in rows:
            tot_debit += to_decimal(r["debit"])
            tot_credit += to_decimal(r["credit"])
            tot_tax += to_decimal(r["tax_amount"])

        return {
            "total_debit": quantize_money(tot_debit),
            "total_credit": quantize_money(tot_credit),
            "total_tax": quantize_money(tot_tax),
            "net_balance": quantize_money(tot_debit - tot_credit)
        }

    def batch_insert(self, rows_data: List[Dict[str, Any]]) -> int:
        if not rows_data:
            return 0
        sql = """
        INSERT INTO transactions (
            engagement_id, file_id, date, voucher_no, invoice_no, ledger,
            account_group, description, debit, credit, amount, tax_amount,
            party_name, gstin, invoice_date, payment_date, reference_no,
            bank_ref, opening_balance, closing_balance, transaction_type, original_row_json
        ) VALUES (
            :engagement_id, :file_id, :date, :voucher_no, :invoice_no, :ledger,
            :account_group, :description, :debit, :credit, :amount, :tax_amount,
            :party_name, :gstin, :invoice_date, :payment_date, :reference_no,
            :bank_ref, :opening_balance, :closing_balance, :transaction_type, :original_row_json
        )
        """
        cursor = self.conn.cursor()
        cursor.executemany(sql, rows_data)
        return cursor.rowcount
