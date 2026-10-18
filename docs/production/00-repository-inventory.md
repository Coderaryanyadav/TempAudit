# 00 — Repository Inventory & Capability Audit

**Repository**: [https://github.com/Coderaryanyadav/TempAudit](https://github.com/Coderaryanyadav/TempAudit)  
**Inspection Date**: October 18, 2026  
**Git Commit**: `3156693b6c7b61c54d8aee5e298dc16177a89d6b`  
**Branch**: `main`  
**Execution Environment**: Python 3.12.15, Node.js v26.11.1, macOS Darwin (Apple Silicon ARM64)  
**Target Audience**: Independent Chartered Accountants, Audit Partners, Technical Buyers, System Architects  

---

## 1. Executive Summary & Purpose

FinAuditPro (TempAudit) is a standalone, offline-first statutory auditing and financial verification suite engineered specifically for Indian Chartered Accountants (CAs). The application operates without cloud dependencies, running against an embedded SQLite database (`backend/finauditpro.db`) with an asynchronous FastAPI backend and a responsive Vanilla JavaScript single-page application (SPA).

### Primary Workflows Supported
1. **Multi-Tenant Audit Engagement Management**: Client master creation, engagement scoping by financial year (e.g. FY 2024-25), role-based assignment (Admin, Auditor, Audit Staff).
2. **Multi-Source Financial Data Ingestion**: Bulk ingestion and normalization of General Ledgers (CSV, XLSX), Sales/Purchase registers, and Bank Statements (CSV, PDF).
3. **Tri-Engine Forensic Audit Analysis**:
   - **Deterministic Engine**: Mathematical checks (Debit == Credit balance), Section 40A(3) cash expense limits, Section 269ST cash receipt aggregations (daily + cross-date transactions), GSTIN structure validation, and chronological sequencing.
   - **Statistical & ML Engine**: Benford's Law first-digit distribution analysis, Scikit-Learn Isolation Forest multi-variate anomaly detection, 3-Sigma Z-Score outlier analysis, and weekend booking spike alerts.
   - **Local AI Assistant**: Contextual natural language explanations grounded strictly in persisted findings with PAN/GSTIN data redaction.
4. **Reconciliation Workbenches**: 4-tier Bank Reconciliation Statement (BRS) engine with strict book-statement source separation, and GSTR-2B vs Books ITC matching.
5. **Cryptographic Audit Trail & Disaster Recovery**: SHA-256 sequential hash chaining on all audit mutations, verified SQLite database snapshots, and safety-tested rollback restoration.

---

## 2. Repository Architecture & Layout

```
TempAudit-main/
├── backend/
│   ├── app/
│   │   ├── audit_engine/          # Deterministic statutory rules & Benford engine
│   │   ├── auth.py                # JWT authentication, Argon2/PBKDF2 hashing, role gating
│   │   ├── database.py            # SQLite connection factory, PRAGMA setup, seeders
│   │   ├── main.py                # FastAPI initialization, CORS, static mounts, router bundle
│   │   ├── parsers/               # CSV, Excel, PDF table parsing & mapping pipelines
│   │   ├── routers/               # 22 RESTful API router modules
│   │   ├── schemas.py             # Pydantic v2 data transfer schemas
│   │   ├── services/              # BRS engine, AI assistant engine, ML models, report generators
│   │   └── utils/                 # Cryptographic audit logger, PAN/GSTIN sanitizers
│   ├── migrations/                # Versioned SQL migrations (001_initial_schema.sql, drop_all.sql)
│   ├── finauditpro.db             # Primary SQLite operational database
│   └── tests/                     # 50 test modules covering 231 pytest assertions
├── frontend/
│   ├── index.html                 # Single-page shell with 21 accessible workspace views
│   ├── css/styles.css             # Unified CSS variables, dark/light themes, typography
│   ├── js/
│   │   ├── api.js                 # API client, token interceptor, download URL signing
│   │   └── app.js                 # State machine, navigation router, view renderers
│   └── tests/                     # Node.js session, token, and download regression suites
├── initialize/                    # Platform launch packages (setup_mac.sh, start_mac.sh, windows .bat)
├── scripts/                       # E2E workflow runners, admin creator, Playwright browser tests
├── DevOps/                        # CI workflow definitions (DevOps/ci/ci.yml)
├── requirements.txt               # Root Python production dependencies
└── README.md                      # Architecture documentation & quickstart guide
```

---

## 3. Capability Inventory & Verification Matrix

| Subsystem | Module / Endpoint | Verified Status | Evidence Reference |
| :--- | :--- | :--- | :--- |
| **Authentication & Session** | `/api/auth/login`, `/me`, `checkAuthSession()` | **Implemented and Verified** | `test_login_session_refresh.py`, Playwright real-browser test |
| **User & Role Gating** | `/api/auth/users`, `/users/{id}/status` | **Implemented and Verified** | `test_auth.py`, role navigation checks |
| **Client Management** | `/api/clients`, `/clients/{id}` | **Implemented and Verified** | `test_clients_engagements.py`, E2E step 04 |
| **Engagement Scoping** | `/api/engagements`, isolation middleware | **Implemented and Verified** | `test_two_companies_isolation.py` |
| **Data Import & Validation** | `/api/import/upload`, `/apply-mapping` | **Implemented and Verified** | `test_import_module.py`, CSV/XLSX parser tests |
| **Trial Balance** | `/api/trial-balance/{engagement_id}` | **Implemented and Verified** | `test_trial_balance_analysis.py`, E2E step 16 |
| **General Ledger** | `/api/transactions/gl/{engagement_id}` | **Implemented and Verified** | `test_general_ledger_analysis.py` |
| **Section 40A(3) Audit** | `DeterministicAuditEngine.check_section_40a3` | **Implemented and Verified** | `test_financial_logic_statutory_rules.py` |
| **Section 269ST Audit** | `DeterministicAuditEngine.check_section_269st` | **Implemented and Verified** | `test_financial_logic_statutory_rules.py` (multi-date tests) |
| **GSTIN Validation** | `DeterministicAuditEngine.check_gstin_validity` | **Implemented and Verified** | Checksum and regex verification tests |
| **Benford's Law Analysis** | `BenfordAnalysisEngine` | **Implemented and Verified** | `test_anomaly_detection_engine.py` |
| **Isolation Forest ML** | `IsolationForestAnomalyModel` | **Implemented and Verified** | `test_ml.py`, Scikit-Learn pipeline tests |
| **Bank Reconciliation** | `run_bank_reconciliation`, `/execute` | **Implemented and Verified** | `test_bank_reconciliation_deep.py` |
| **GST 2B Reconciliation** | `/api/gst-reconciliation/match` | **Implemented and Verified** | `test_gst_reconciliation.py` |
| **Local AI Assistant** | `/api/assistant/ask`, `/explain-finding` | **Implemented and Verified** | `test_local_ai_assistant.py`, zero fabrication test |
| **ReportLab PDF Generation** | `/api/reports/generate-pdf/{eng_id}` | **Implemented and Verified** | `test_reports_module.py`, PDF binary validation |
| **Tamper-Evident Trail** | `log_audit_event`, SHA-256 chain | **Implemented and Verified** | `test_audit_trail_and_backup.py` |
| **Backup & Restore** | `/api/settings/backup/create`, `/restore` | **Implemented and Verified** | `test_verified_backup_and_integrity_dashboard.py` |
| **Real Browser Refresh** | Chromium Playwright runner | **Implemented and Verified** | `scripts/test_real_browser_full_journey.py` |
| **CI Automation** | `DevOps/ci/ci.yml` | **Implemented but Manual Step**| Requires OAuth `workflow` scope on GitHub remote |

---

## 4. External Dependencies & Offline Boundaries

- **Python Packages**: FastAPI, Uvicorn, Pydantic v2, PyJWT, Pandas, OpenPyXL, ReportLab, Scikit-Learn, SciPy, NumPy, PyPDF, XLrd, Pytest, Playwright.
- **Frontend Dependencies**: 100% Vanilla JS, HTML5, CSS3. Zero external CDNs; zero analytics or tracking beacons.
- **Network Boundaries**: 
  - The application binds exclusively to `127.0.0.1` / `localhost`.
  - The local AI client only queries `http://localhost:1234` (LM Studio) or local Ollama endpoints. If unavailable, it falls back to 100% offline deterministic audit explanations.
