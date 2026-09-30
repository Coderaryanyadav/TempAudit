# FinAuditPro - Developer & Architecture Guide

## 1. Codebase Organization

```
TempAudit-main/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI core app & CORS configuration
│   │   ├── auth.py                     # JWT token generation, bcrypt hashing & RBAC
│   │   ├── database.py                 # SQLite initialization & connection factory
│   │   ├── routers/
│   │   │   ├── auth.py                 # /api/auth (login, me)
│   │   │   ├── clients.py              # /api/clients (CRUD, engagements)
│   │   │   ├── transactions.py         # /api/transactions
│   │   │   ├── audit.py                # /api/audit (rules engine, anomalies)
│   │   │   ├── import_export.py        # /api/import-export (parsers & pre-validation)
│   │   │   ├── reconciliation.py       # /api/reconciliation (bank & GST)
│   │   │   ├── trial_balance.py        # /api/trial-balance (TB & GL analysis)
│   │   │   ├── financial_analysis.py   # /api/financial-analysis (ratios & health)
│   │   │   ├── yoy.py                  # /api/yoy (prior vs current year)
│   │   │   ├── findings.py             # /api/findings (risk register & sync)
│   │   │   ├── checklist.py            # /api/checklist (statutory compliance)
│   │   │   ├── working_papers.py       # /api/working-papers (SA 230 papers)
│   │   │   ├── reports.py              # /api/reports (PDF report generation)
│   │   │   ├── audit_trail.py          # /api/audit-trail (immutable logs & backups)
│   │   │   ├── dashboard.py            # /api/dashboard (aggregated overview & charts)
│   │   │   └── ai_manager.py           # /api/ai-manager (LM Studio AI config)
│   │   ├── services/
│   │   │   ├── audit_rules.py          # Deterministic rules (Sec 40A(3), 269ST, duplicates)
│   │   │   ├── ml_audit.py             # Isolation Forest & Benford's Law
│   │   │   ├── reconciliation_service.py # BRS & GST 2B matchers
│   │   │   ├── local_ai_provider.py    # LMStudioProvider & Privacy Shield
│   │   │   ├── local_ai_assistant_engine.py # Intent extraction, query router & NLP responses
│   │   │   ├── pdf_report_service.py   # ReportLab deterministic PDF generation
│   │   │   ├── dashboard_service.py    # SQL aggregation for metrics and charts
│   │   │   └── audit_trail_service.py  # Immutable event logging & backup/restore
│   │   └── utils/
│   │       └── sample_data.py          # Test dataset generator for automated tests
│   ├── finauditpro.db                  # Local SQLite database
│   ├── reports_generated/              # Output PDF storage
│   ├── sample_files/                   # Sample test Excel & CSV files
│   └── tests/                          # Automated Pytest suite
├── frontend/
│   ├── index.html                      # Single Page Application structure
│   ├── css/
│   │   └── styles.css                  # Modern UI tokens, cards, modals & dark accents
│   └── js/
│       ├── api.js                      # REST API client
│       └── app.js                      # Core SPA router, controllers & modals
├── docs/                               # Complete project documentation suite
├── .env                                # Production environment configuration
├── setup.bat                           # Windows setup script
├── start.bat                           # Windows start script
├── requirements.txt                    # Python runtime dependencies
└── run.py                              # Unified desktop launcher
```

---

## 2. Core Architectural Principles

### 2.1 Multi-Tenant Data Isolation
Every API endpoint requires `engagement_id` (and/or `client_id`). Database queries are strictly scoped:
```python
cursor.execute("SELECT * FROM transactions WHERE engagement_id = ?", (engagement_id,))
```
Cross-client data leakage is structurally impossible.

### 2.2 Deterministic Calculations vs AI Explanations
- **Zero Hallucinated Numbers:** All balances, variances, tax reconciliations, ratio calculations, and Benford distributions are computed via deterministic Python algorithms and SQL aggregates.
- **AI Role:** LM Studio is solely employed to generate contextual summaries, explain why a specific transaction violated a statutory rule, and assist in drafting auditor observations.

### 2.3 Privacy Shield & Data Sanitization
Before any prompt or query context is passed to LM Studio, the `sanitize_audit_text()` pipeline automatically redacts sensitive data:
- PAN numbers (`[PAN_REDACTED]`)
- GSTIN IDs (`[GSTIN_REDACTED]`)
- Bank Account Numbers (`[BANK_ACCT_REDACTED]`)
- Client Names (`[ENTITY_UNDER_AUDIT]`)
- Email addresses and Phone numbers (`[EMAIL_REDACTED]`, `[PHONE_REDACTED]`)

---

## 3. Pluggable Local AI Provider Interface

FinAuditPro communicates with local LLMs via `LMStudioProvider` in [backend/app/services/local_ai_provider.py](file:///c:/Users/sbmpc.student/Desktop/TempAudit-main/backend/app/services/local_ai_provider.py):

```python
class LMStudioProvider(BaseLocalAIProvider):
    def check_health(self) -> Tuple[bool, str, float]:
        """Checks GET http://localhost:1234/v1/models"""
        ...

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2, max_tokens: int = 2048) -> Dict[str, Any]:
        """Calls POST http://localhost:1234/v1/chat/completions"""
        ...
```

If LM Studio is disconnected or offline, the system falls back gracefully to `BuiltinDeterministicAIProvider` while displaying:
`"LM Studio is not connected. AI assistance is unavailable, but audit calculations and analysis remain available."`
