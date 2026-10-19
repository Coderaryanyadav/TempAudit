# Repository Architecture & Directory Taxonomy

## 1. High-Level Taxonomy

```
TempAudit/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated GitHub Actions CI pipeline
├── backend/
│   ├── app/
│   │   ├── audit_engine/          # Deterministic statutory audit engines
│   │   ├── parsers/               # Multi-format financial data ingest (CSV, Excel)
│   │   ├── repositories/          # SQLite persistence & query abstraction
│   │   ├── routers/               # FastAPI modular REST endpoints (21 modules)
│   │   ├── services/              # Business logic, reconciliations, local AI synthesis
│   │   ├── utils/                 # Currency formatting, PDF generation, audit logging
│   │   ├── auth.py                # PBKDF2/HMAC authentication & RBAC middleware
│   │   ├── database.py            # SQLite schema initialization & database connection pooling
│   │   ├── main.py                # FastAPI ASGI application factory & route registration
│   │   └── schemas.py             # Pydantic data schemas & validation models
│   ├── backups/                   # Encrypted, HMAC-signed database backups
│   ├── logs/                      # Application audit and execution logs
│   ├── migrations/                # Versioned SQL migration scripts & schema runner
│   ├── reports_generated/         # Generated PDF and CSV audit reports
│   ├── sample_files/              # Reference audit test files (General Ledgers, GSTR-2B)
│   ├── tests/                     # 50 comprehensive Pytest test suites
│   └── uploaded_files/            # Client audit evidentiary document store
├── frontend/
│   ├── css/
│   │   └── styles.css             # Enterprise CA design system, responsive KPI & stat grid
│   ├── js/
│   │   ├── api.js                 # Offline API client with token lifecycle management
│   │   └── app.js                 # Single-Page Application router, reactive state & UI
│   ├── tests/                     # Node.js automated regression and session tests
│   └── index.html                 # Single-Page Application entry point
├── docs/
│   ├── architecture/              # High-level architecture and system design
│   ├── deployment/                # Local desktop and container deployment guides
│   ├── development/               # Developer setup, coding standards, and testing guides
│   ├── maintenance/               # Repository audit, structure, and cleanup reports
│   ├── production/                # Operational manuals, statutory formulas, release readiness
│   └── production-review/         # Comprehensive release scorecards and defect verification
├── initialize/                    # Platform-specific initializers and runners
│   ├── setup_mac.sh               # macOS environment setup and dependency installer
│   ├── start_mac.sh               # macOS runner with LM Studio auto-start & model loading
│   ├── setup_windows.bat          # Windows environment setup batch script
│   └── start_windows.bat          # Windows runner batch script
├── scripts/                       # Operational utilities and test automation scripts
│   ├── activate_github_ci_workflow.sh
│   ├── clean_room_reset.py        # Reset database to pristine state for verification
│   ├── cleanup_generated.sh       # Safe cache & temporary artifact cleanup script
│   ├── create_admin.py            # Interactive CLI administrator account creation
│   ├── e2e_full_audit_workflow.py # 24-step end-to-end statutory audit verification
│   └── seed_test_data.py          # Synthetic corporate data seeder
├── test_data/                     # Synthetic test fixtures & mock business records
│   ├── aryan_fintech/             # Complete statutory & tax audit test data suite
│   ├── hitansh_fintech/           # Secondary isolated entity for multi-tenant tests
│   └── generator.py               # Deterministic synthetic ledger generator
├── DevOps/                        # Infrastructure, Docker, and deployment configurations
│   ├── docker/                    # Container Dockerfile
│   └── ci/                        # Reference CI workflow manifests
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git exclusion rules
├── compose.yaml                   # Docker Compose specification
├── pyproject.toml                 # Python packaging and tool configuration
├── pytest.ini                     # Pytest runner configuration
├── requirements.txt               # Production Python runtime dependencies
├── requirements.lock              # Pinned dependency hashes
├── run.py                         # Standalone desktop server runner
└── README.md                      # Primary project overview, quickstart, and documentation
```

## 2. Invariant Design Rules

1. **Root Cleanliness**: Only core entry points (`run.py`), dependency manifests, and standard configuration reside at the root.
2. **Offline-First Principle**: FinAuditPro executes 100% locally on localhost without requiring internet access or cloud daemons.
3. **Data Safety Guarantee**: Application database (`backend/finauditpro.db`), uploaded files, backups, and reports are strictly excluded from git tracking and protected against accidental resets.
