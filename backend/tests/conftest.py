"""
Pytest Configuration & Isolated Test Database Setup
FinAuditPro - Test Isolation

Ensures that all test suites execute in an isolated test database (`test_audit_db.db`),
leaving the main application database (`finauditpro.db`) clean with only the two
official test companies (Aryan Fintech Pvt. Ltd. and Hitansh Fintech Pvt. Ltd.).
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure repository root is on sys.path for IDEs and direct pytest runs
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Determine isolated test database path
configured_path = os.environ.get("FINAUDIT_DB_PATH")
default_test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_audit_db.db")

# Strict safeguard: Never allow tests to execute against the production database
if configured_path and os.path.basename(os.path.abspath(configured_path)) == "finauditpro.db":
    TEST_DB_PATH = default_test_path
else:
    TEST_DB_PATH = configured_path or default_test_path

os.environ["FINAUDIT_DB_PATH"] = TEST_DB_PATH

if not os.environ.get("FINAUDIT_SECRET_KEY") and not os.environ.get("FINAUDIT_BACKUP_SIGNING_KEY"):
    os.environ["FINAUDIT_SECRET_KEY"] = "test_suite_secret_key_for_testing_purposes_only_1234567890"

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
