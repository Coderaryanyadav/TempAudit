# Comprehensive Repository Audit & Asset Inventory

**Date of Audit:** October 19, 2026  
**Repository:** `TempAudit` / `FinAuditPro`  
**Current Branch:** `main`  
**Latest Verified Commit:** `4580edc`  
**Architecture:** 100% Offline-First, Single-Tenant Desktop / Local Web Architecture (FastAPI + SQLite + Vanilla JS SPA)

---

## 1. Executive Summary & Inventory Classification

This document represents the baseline repository inventory performed prior to structural maintenance and professional reorganization. Every file and directory has been verified and classified according to its functional role within the codebase.

### Classification Categories (9 Core Domains)

| Category ID | Classification Domain | Scope & Description |
| :--- | :--- | :--- |
| **1** | **Application Source Code** | Core backend logic, FastAPI routers, services, repositories, deterministic audit engines, frontend HTML/CSS/JS. |
| **2** | **Tests & Synthetic Fixtures** | Pytest backend test suite, Node.js frontend tests, synthetic corporate fixtures (Aryan Fintech & Hitansh Fintech). |
| **3** | **Required Configuration** | `pytest.ini`, `pyproject.toml`, Docker `compose.yaml`, `.gitignore`. |
| **4** | **Documentation** | System architecture, audit rules & formulas, user manual, and operational guides under `docs/`. |
| **5** | **Dependency & Environment Files** | `requirements.txt`, `requirements.lock`, Python `pyproject.toml`. |
| **6** | **Generated Artifacts** | Build outputs, coverage outputs (`.coverage`), egg-info, pytest cache. |
| **7** | **Runtime Data** | Production SQLite database (`backend/finauditpro.db`), uploaded files, generated reports, database backups. |
| **8** | **Potentially Sensitive Data** | JWT secrets, encryption keys, local database records (safeguarded via local-only architecture). |
| **9** | **Obsolete / Disposable Files** | Temporary text notes, OS artifacts (`.DS_Store`), bytecode caches (`__pycache__`). |

---

## 2. Granular Inventory Breakdown

### Category 1: Application Source Code
- **Backend Entry Point:** [run.py](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/run.py) (Launches Uvicorn server at `127.0.0.1:8000`)
- **Backend Core Framework:** [backend/app/main.py](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/backend/app/main.py), [backend/app/database.py](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/backend/app/database.py), [backend/app/auth.py](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/backend/app/auth.py), [backend/app/schemas.py](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/backend/app/schemas.py)
- **FastAPI Subsystem Routers (21 Modules):** `backend/app/routers/` (Authentication, Dashboard, Trial Balance, General Ledger, Reconciliations, Audit Findings, Working Papers, Reports, AI Manager, Settings)
- **Deterministic Business Services (18 Modules):** `backend/app/services/` (Deterministic audit engine, Trial balance analyzer, Bank reconciliation, GST matching, Centralized findings, AI assistant engine)
- **Data Access & Parsers:** `backend/app/repositories/`, `backend/app/parsers/`
- **Frontend Architecture:**
  - Single-Page Application HTML: [frontend/index.html](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/frontend/index.html)
  - UI State & Reactive Rendering: [frontend/js/app.js](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/frontend/js/app.js)
  - API Client & Token Management: [frontend/js/api.js](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/frontend/js/api.js)
  - Enterprise CSS Design System: [frontend/css/styles.css](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/frontend/css/styles.css)

### Category 2: Tests & Synthetic Test Fixtures
- **Backend Pytest Suite (50 Test Modules):** [backend/tests/](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/backend/tests/)
  - Covers statutory rules, financial invariants, authentication security, role isolation, multi-tenant separation, backup HMAC validation, and AI assistant evidence provenance.
- **Frontend Automated Tests:**
  - `frontend/tests/test_login_session_refresh.js`
  - `frontend/tests/test_api_client_and_download_tokens.js`
- **Synthetic Corporate Fixtures:**
  - `test_data/aryan_fintech/`: Bank statements, sales registers, purchase registers, GST portal downloads, prior year data.
  - `test_data/hitansh_fintech/`: Independent synthetic company transactions for cross-company isolation verification.
  - Python Fixture Generators: `test_data/generator.py`, `test_data/seed.py`, `test_data/transactions.py`

### Category 3: Required Configuration
- Pytest Configuration: [pytest.ini](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/pytest.ini)
- Project & Build Metadata: [pyproject.toml](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/pyproject.toml)
- Git Exclusion Rules: [.gitignore](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/.gitignore)
- Container Orchestration: [compose.yaml](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/compose.yaml), `DevOps/docker/Dockerfile`

### Category 4: Documentation
- Root Documentation: [README.md](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/README.md)
- Production System Guides: `docs/production/` (00-18 technical architecture, statutory rules, user manual, and release readiness)
- External Audit & Code Review Scorecards: `docs/production-review/` (00-11 executive review, defect logs, and scorecards)

### Category 5: Dependencies & Environment Manifests
- Production Requirements: [requirements.txt](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/requirements.txt)
- Pinned Hashes & Lockfile: [requirements.lock](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/requirements.lock)
- Python Packaging: [pyproject.toml](file:///Users/aryan/Desktop/PROJECTS/TempAudit-main/pyproject.toml)

### Category 6: Generated Artifacts (Disposable)
- Test Coverage Cache: `.coverage`
- Pytest Caches: `.pytest_cache/`
- Python Build Info: `tempaudit.egg-info/`

### Category 7: Runtime Data (Persistent & Safeguarded)
- Production SQLite Database: `backend/finauditpro.db`
- Client Upload Storage: `backend/uploaded_files/`
- Generated PDF/CSV Reports: `backend/reports_generated/`
- Encrypted Application Backups: `backend/backups/`
- Execution Logs: `backend/logs/`

### Category 8: Potentially Sensitive Data
- Database JWT Key & Audit Trail: Stored within protected SQLite `app_settings` table in `finauditpro.db`.
- *Finding:* No live production secrets or private keys are committed to Git. All sample keys in scripts use synthetic testing strings.

### Category 9: Obsolete / Disposable Files (Flagged for Cleanup)
- `Test.txt` in root: Contains temporary manual console commands from a past demo. Flagged for safe removal.
- `.DS_Store` in root: macOS metadata file. Flagged for removal.
- `uploaded_files/` in root: Redundant empty directory (actual upload directory is `backend/uploaded_files/`).
