import unittest
from backend.app.audit_engine.statistical import StatisticalAuditEngine

class TestStatisticalAuditEngine(unittest.TestCase):
    def test_benfords_law_computation(self):
        # Generate synthetic numbers
        transactions = []
        for i in range(100):
            transactions.append({
                "id": i,
                "amount": float(i * 123.45 + 10),
                "debit": float(i * 123.45 + 10),
                "credit": 0.0,
                "date": "2024-05-15",
                "ledger": "Test Expense"
            })
        engine = StatisticalAuditEngine(transactions)
        res = engine.analyze_benfords_law()
        self.assertIn("digit_distribution", res)
        self.assertEqual(len(res["digit_distribution"]), 9)

    def test_isolation_forest_execution(self):
        transactions = []
        # Normal cluster
        for i in range(50):
            transactions.append({
                "id": i,
                "amount": 1000.0 + (i % 10) * 50,
                "debit": 1000.0 + (i % 10) * 50,
                "credit": 0.0,
                "date": "2024-05-15",
                "ledger": "Office Supplies"
            })
        # Extreme outlier
        transactions.append({
            "id": 999,
            "amount": 5000000.0,
            "debit": 5000000.0,
            "credit": 0.0,
            "date": "2024-05-15",
            "ledger": "Office Supplies"
        })
        engine = StatisticalAuditEngine(transactions)
        res = engine.detect_isolation_forest_outliers()
        self.assertEqual(res["status"], "completed")
        self.assertGreater(res["outliers_count"], 0)

if __name__ == "__main__":
    unittest.main()
