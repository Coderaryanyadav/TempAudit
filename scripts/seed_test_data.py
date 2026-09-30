#!/usr/bin/env python3
"""
Test Data Seeder Script
TempAudit - Audit Application

Populates the SQLite database with the two independent test companies:
- Aryan Fintech Pvt. Ltd. (ARYAN)
- Hitansh Fintech Pvt. Ltd. (HITANSH)

Usage:
    python scripts/seed_test_data.py
    or:
    python -m test_data.seed
"""

import sys
import os

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_data.seed import seed_test_database

if __name__ == "__main__":
    print("Seeding FinAuditPro test database with test entities...")
    result = seed_test_database()
    print("Successfully seeded test database:")
    print(f"  - Aryan Fintech: CY Engagement #{result['aryan']['cy_engagement_id']} (FY 2025-26), PY #{result['aryan']['py_engagement_id']}")
    print(f"  - Hitansh Fintech: CY Engagement #{result['hitansh']['cy_engagement_id']} (FY 2025-26), PY #{result['hitansh']['py_engagement_id']}")
    print("Test users created:")
    print("  - Admin: admin / admin123")
    print("  - Aryan Auditor: auditor_aryan / audit123 (Staff: staff_aryan / staff123)")
    print("  - Hitansh Auditor: auditor_hitansh / audit123 (Staff: staff_hitansh / staff123)")
