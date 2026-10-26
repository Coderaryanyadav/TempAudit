# FinAuditPro Operational Utilities & Automation Scripts

This directory houses maintenance utilities, database seeding tools, testing runners, automated browser suites, cross-platform launchers, and enterprise deliverable generators.

---

## Script Inventory by Category

### 1. Platform Setup & Launchers (macOS, Linux & Windows)

| Script | Purpose & Description | Execution Command |
| :--- | :--- | :--- |
| [`setup_mac.sh`](setup_mac.sh) | **macOS / Linux Environment Setup:** Verifies Python 3.10+, provisions `venv`, installs locked dependencies, creates runtime data directories, initializes clean database schema, and prompts for admin creation. | `./scripts/setup_mac.sh` |
| [`start_mac.sh`](start_mac.sh) | **macOS / Linux Daily Launcher:** Loads environment variables, activates virtualenv, checks database schema & admin existence, probes local LM Studio AI daemon, and launches the web interface. | `./scripts/start_mac.sh` |
| [`setup_windows.bat`](setup_windows.bat) | **Windows Environment Setup:** Windows batch installer that checks Python runtime, provisions virtualenv, installs pip packages, creates data directories, and initializes the database. | `scripts\setup_windows.bat` |
| [`start_windows.bat`](start_windows.bat) | **Windows Daily Launcher:** Activates virtualenv, verifies database, tests local LM Studio AI status, and boots FastAPI desktop server via `python run.py`. | `scripts\start_windows.bat` |

### 2. Testing, Verification & UI Automation

| Script | Purpose & Description | Execution Command |
| :--- | :--- | :--- |
| [`run_tests.sh`](run_tests.sh) | **Universal Test Runner:** Automatically targets the local virtual environment's pytest binary with arbitrary arguments. | `./scripts/run_tests.sh [pytest-options]` |
| [`test_browser_suite.py`](test_browser_suite.py) | **Consolidated Real Browser Suite:** Unified Playwright E2E suite covering authentication & session persistence, form boundary inputs, and full 21-screen audit journey. Supports modular `--auth`, `--forms`, and `--journey` flags. | `python scripts/test_browser_suite.py [--auth\|--forms\|--journey]` |
| [`take_all_screenshots.py`](take_all_screenshots.py) | **Ultra-HD 4K Screenshot Suite:** Headless browser automation capturing pixel-perfect, Retina 2x screenshots across all 22 frontend audit routes into `docs/screenshots/`. | `python scripts/take_all_screenshots.py` |
| [`e2e_full_audit_workflow.py`](e2e_full_audit_workflow.py) | **Headless E2E Verification:** Automated 24-step statutory audit lifecycle verification testing the backend API pipeline from ingestion to final sign-off. | `python scripts/e2e_full_audit_workflow.py` |

### 3. Database Seeding & Administration

| Script | Purpose & Description | Execution Command |
| :--- | :--- | :--- |
| [`reset_and_seed_aryan_fintech.py`](reset_and_seed_aryan_fintech.py) | **Gold-Standard Corporate Seeder:** Generates 1,097 verified General Ledger records across 26 accounts for Aryan Fintech Pvt. Ltd. (FY 2025-26 & FY 2024-25), with realistic Indian corporate banking, GST, and payroll journals. | `python scripts/reset_and_seed_aryan_fintech.py` |
| [`seed_test_data.py`](seed_test_data.py) | **Multi-Company Test Seeder:** Seeds standard multi-tenant test entities (*Aryan Fintech Pvt. Ltd.* and *Hitansh Fintech Pvt. Ltd.*) with sample users, engagements, and trial balance lines. | `python scripts/seed_test_data.py` |
| [`clean_room_reset.py`](clean_room_reset.py) | **Clean-Room Reset & Invariant Verifier:** Archives the database, wipes temporary artifacts, re-runs schema migrations, and asserts strict zero-data invariants across all tables. | `python scripts/clean_room_reset.py --confirm-reset` |
| [`create_admin.py`](create_admin.py) | **CLI Admin Creator:** Interactive and non-interactive command-line utility to bootstrap administrator credentials with PBKDF2/bcrypt hashing directly into the database. | `python scripts/create_admin.py` |
| [`drop_all.py`](drop_all.py) | **Schema Drop Utility:** Drops all database tables and triggers for migration lifecycle testing. *(CAUTION: Destructive - test environments only)* | `python scripts/drop_all.py` |

### 4. Enterprise Deliverables, Maintenance & CI

| Script | Purpose & Description | Execution Command |
| :--- | :--- | :--- |
| [`generate_reports_and_docs.py`](generate_reports_and_docs.py) | **Enterprise Deliverables Generator:** Synthesizes master PDF deliverables into `backend/reports_generated/master_deliverables/` including the 10-report audit compendium with bookmarks and the comprehensive architectural documentation manual. | `python scripts/generate_reports_and_docs.py` |
| [`cleanup_generated.sh`](cleanup_generated.sh) | **Safe Cache & Artifact Cleaner:** Discovers and purges Python bytecode (`__pycache__`, `*.pyc`), test caches (`.pytest_cache`), and disposable temporary files. Dry-run by default. | `./scripts/cleanup_generated.sh [--apply]` |
| [`activate_github_ci_workflow.sh`](activate_github_ci_workflow.sh) | **CI Deployment Helper:** Deploys and validates the automated continuous integration workflow manifest into `.github/workflows/ci.yml`. | `./scripts/activate_github_ci_workflow.sh` |
| [`push_to_github.sh`](push_to_github.sh) | **Git Push Helper:** Convenience script to verify current branch status and synchronize verified changes with the remote GitHub repository. | `./scripts/push_to_github.sh` |

---

## Safety Constraints & Invariants

- **Dry-Run by Default:** Maintenance scripts such as `cleanup_generated.sh` default to read-only simulation unless `--apply` or `--force` is explicitly passed.
- **Production Safeguards:** Scripts modifying database schemas (e.g., `clean_room_reset.py`) explicitly inspect the environment (`FINAUDIT_ENV`) and abort if executed in production.
- **Self-Contained & Offline:** All scripts operate strictly against local runtime endpoints (`localhost:8000`, local SQLite database) and emit zero external telemetry.
