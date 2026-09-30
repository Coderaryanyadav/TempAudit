# FinAuditPro — Technical Architecture

FinAuditPro implements a 3-tier hybrid audit architecture engineered specifically for independent Chartered Accountants and audit seniors in India.

```
                               ┌─────────────────────────────┐
                               │   FinAuditPro Desktop UI    │
                               │ (HTML5/CSS3/Vanilla JS SPA) │
                               └──────────────┬──────────────┘
                                              │
                               ┌──────────────▼──────────────┐
                               │    FastAPI Backend Server   │
                               │   (100% Local & Offline)    │
                               └──────────────┬──────────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     │                        │                        │
      ┌──────────────▼──────────────┐ ┌───────▼──────────────┐ ┌───────▼──────────────┐
      │ 1. Deterministic Rule Engine│ │2. Statistical / ML   │ │3. Local LM Studio    │
      ├─────────────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
      │• Debit = Credit check       │ │• Benford's Law (1-9) │ │• OpenAI-Compatible   │
      │• Section 40A(3) (₹10k cash) │ │• Scikit-Learn        │ │  Localhost:1234 API  │
      │• Section 269ST (₹2L cash)   │ │  Isolation Forest    │ │• PII Privacy Shield  │
      │• GSTIN 15-char validation   │ │• 3-Sigma Z-Score     │ │• Deterministic Fact  │
      │• Duplicate transaction hash │ │• Weekend timing spike│ │  Grounding           │
      │• Date & chronology mismatch │ │• Outlier Score       │ │• Zero Cloud Leakage  │
      └─────────────────────────────┘ └──────────────────────┘ └──────────────────────┘
                                              │
                               ┌──────────────▼──────────────┐
                               │     Local SQLite Database   │
                               │     (`finauditpro.db`)      │
                               │  Trigger Immutable Trail    │
                               └─────────────────────────────┘
```

---

## 1. Hybrid 3-Tier Execution Pipeline

### Tier 1: Deterministic Audit Engine
- **Trial Balance Mathematical Equality:** Calculates exact $Total\,Dr == Total\,Cr$ and flags discrepancies.
- **Income Tax Act Section 40A(3):** Flags cash expenditures exceeding ₹10,000 to any party in a single day (Clause 21(d) Form 3CD).
- **Income Tax Act Section 269ST:** Flags cash receipts of ₹2,00,000 or more (Clause 31 Form 3CD).
- **GSTIN 15-Character Checksum:** Verifies State Code + PAN + Entity Code + Z + Check Digit.
- **Duplicate Detection:** Exact & Fuzzy string similarity matching on invoice numbers and amounts.
- **Sequential Gap Detection:** Identifies missing voucher, invoice, or cheque numbers in continuous ranges.

### Tier 2: Statistical & Machine Learning Engine
- **Benford's Law First-Digit Analysis (Nigrini Forensic Standard):** Computes empirical digit distributions against theoretical log distribution with Mean Absolute Deviation (MAD).
- **Isolation Forest (Scikit-Learn):** Multi-variate outlier anomaly scoring across amount, debit, credit, day-of-week, and day-of-month features.

### Tier 3: Local AI Assistant via LM Studio
- **Privacy Shield:** Sanitizes all input text using regex scrubbers to redact PANs, GSTINs, bank accounts, and client names before model ingestion.
- **Evidence-Grounded Querying:** First retrieves database transactions and deterministic rule results, passing verifiable evidence to LM Studio.
- **Zero Hallucination Guarantee:** Never fabricates missing transactions or financial figures. If an item is not found, states: *"No matching transaction was found in the current engagement."*

---

## 2. Directory Layout & Separation of Concerns

```
TempAudit-main/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application & router mounting
│   │   ├── auth.py                     # PBKDF2 cryptography & JWT tokens
│   │   ├── database.py                 # SQLite init, schema & triggers
│   │   ├── routers/                    # Modular REST API endpoints
│   │   │   ├── auth.py
│   │   │   ├── clients.py
│   │   │   ├── engagements.py
│   │   │   ├── import_data.py
│   │   │   ├── trial_balance.py
│   │   │   ├── reconciliation.py
│   │   │   ├── gst_reconciliation.py
│   │   │   ├── anomalies.py
│   │   │   ├── audit_findings.py
│   │   │   ├── working_papers.py
│   │   │   ├── reports.py
│   │   │   ├── audit_trail.py
│   │   │   ├── ai_manager.py           # LM Studio configuration router
│   │   │   └── settings.py
│   │   └── services/                   # Business logic & algorithms
│   │       ├── local_ai_provider.py    # LMStudioProvider & Privacy Shield
│   │       ├── local_ai_assistant_engine.py
│   │       ├── anomaly_detection_engine.py
│   │       ├── bank_reconciliation_engine.py
│   │       ├── gst_reconciliation_engine.py
│   │       ├── trial_balance_analyzer.py
│   │       ├── general_ledger_analyzer.py
│   │       └── pdf_report_service.py
│   ├── finauditpro.db                  # Local production SQLite database
│   ├── backups/                        # Timestamped DB backups
│   ├── uploaded_files/                 # Uploaded ledger/bank/GST files
│   ├── reports_generated/              # Output PDF audit reports
│   └── tests/                          # Pytest automated test suite
├── frontend/                           # Single Page Application
│   ├── index.html                      # HTML5 layout & modal overlays
│   ├── css/styles.css                  # UI styling & tokens
│   └── js/
│       ├── api.js                      # REST API client
│       └── app.js                      # Application controller & view routers
├── .env                                # Local environment configuration
├── setup.bat                           # Windows one-click installer
├── start.bat                           # Windows launch script
├── run.py                              # Python desktop runner
└── requirements.txt                    # Production dependencies
```
