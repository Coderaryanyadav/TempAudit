"""
Pytest Configuration & Isolated Test Database Setup
FinAuditPro - Test Isolation

Ensures that all test suites execute in an isolated test database (`test_audit_db.db`),
leaving the main application database (`finauditpro.db`) clean with only the two
official test companies (Aryan Fintech Pvt. Ltd. and Hitansh Fintech Pvt. Ltd.).
"""

import os
import pytest

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_audit_db.db")
os.environ["FINAUDIT_DB_PATH"] = TEST_DB_PATH

from backend.app.database import init_db
from test_data.seed import seed_test_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Initializes isolated database for test execution."""
    os.environ["FINAUDIT_DB_PATH"] = TEST_DB_PATH
    init_db()
    seed_test_database()
    yield
    # Cleanup test db after session
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
