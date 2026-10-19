# FinAuditPro Operational Utilities & Automation Scripts

This directory houses maintenance utilities, database seeding tools, testing runners, and automated verification scripts.

---

## Script Inventory

| Script | Purpose & Usage | Execution Command |
| :--- | :--- | :--- |
| `cleanup_generated.sh` | Safely cleans bytecode, test caches, and disposable temporary files. Defaults to dry-run mode. | `./scripts/cleanup_generated.sh [--force]` |
| `create_admin.py` | Interactive CLI for creating an initial Administrator user account without web UI. | `python scripts/create_admin.py` |
| `seed_test_data.py` | Seeds the local SQLite database with realistic corporate audit test data (Apex Global Logistics / Bharat Forge). | `python scripts/seed_test_data.py` |
| `e2e_full_audit_workflow.py` | Complete 24-step headless end-to-end statutory audit verification. | `python scripts/e2e_full_audit_workflow.py` |
| `clean_room_reset.py` | Reinitializes a clean production database schema for verification testing. | `python scripts/clean_room_reset.py` |
| `drop_all.py` | Drops all tables for migration testing. *(CAUTION: Destructive - use only in test environments)* | `python scripts/drop_all.py` |
| `activate_github_ci_workflow.sh` | Deploys the CI pipeline manifest into `.github/workflows/ci.yml`. | `./scripts/activate_github_ci_workflow.sh` |
| `test_real_browser_auth.py` | Real-browser automated test verifying login, JWT session persistence, and logout. | `python scripts/test_real_browser_auth.py` |
| `test_real_browser_deep_input.py` | Real-browser input boundary verification on financial forms. | `python scripts/test_real_browser_deep_input.py` |
| `test_real_browser_full_journey.py` | Full visual browser automation traversing all 16 audit modules. | `python scripts/test_real_browser_full_journey.py` |

---

## Safety Constraints

- **Non-Destructive by Default:** Scripts never delete or overwrite the production database unless explicitly targeted.
- **Dry-Run by Default:** `cleanup_generated.sh` only displays files to be removed unless `--force` or `--apply` is specified.
- **Offline Assurance:** None of the scripts transmit telemetry or data outside localhost.
