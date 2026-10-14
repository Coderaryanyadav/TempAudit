# TempAudit / FinAuditPro — DevOps SLA Practical Pack (2026)

This pack contains starter files and a step-by-step practical guide for the five DevOps SLA tasks using the existing [TempAudit repository](https://github.com/Coderaryanyadav/TempAudit).

## Repository fit

- Python FastAPI backend, HTML/CSS/JavaScript frontend.
- App URL: `http://127.0.0.1:8000`; health check: `/api/health`.
- Authentication endpoints use `/api/auth/`, including `/api/auth/setup-status`, `/api/auth/initial-setup`, and `/api/auth/login`.
- Existing database layer is SQLite (`backend/app/database.py`). No external SQL server is required for a basic database-persistence demonstration.
- On fresh setup, use the first-run setup wizard to create a demo administrator. Do not hardcode or reuse passwords in the report.

## Files

- `docs/DEVOPS_SLA_GUIDE.md` — complete five-task guide, commands, verification and screenshot checklist.
- `docker/Dockerfile`, `docker/compose.yaml`, `docker/.env.example`, `docker/.dockerignore` — container starter files.
- `selenium/test_smoke.py`, `selenium/requirements-test.txt` — real smoke tests for the homepage, health check and setup-state endpoint.
- `ansible/tempaudit_setup.yml`, `ansible/inventory-local.ini` — provisioning/deployment playbook that installs dependencies, creates a systemd service, and checks the app on an Ubuntu/Debian target.

## Important Docker copy note

Copy the `docker/` directory's files into the repository's root `tempaudit_devops_pack/docker/` directory, or adjust the Compose `build.context`/`dockerfile` paths to suit where the pack is stored. The supplied Compose file assumes this pack is stored inside the repository at `tempaudit_devops_pack/`. A Dockerfile-specific ignore file is included alongside the Dockerfile so local `.env`, local database files and generated outputs are excluded from build context.

Do not run `docker compose down -v` if you need to preserve your demo data; `-v` deletes the named volumes.

## Evidence integrity

The screenshots in the final submission must be captured from your own successful runs. This pack does not claim Jenkins, Docker, Selenium, or Ansible have been run on your device. Capture evidence only after the corresponding commands succeed.
