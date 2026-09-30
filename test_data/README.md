# FinAuditPro Test Data Architecture

This directory provides a completely independent, deterministic, and auditable test-data subsystem for **FinAuditPro**.

## 1. Test Companies

### Company 1: Aryan Fintech Pvt. Ltd. (ARYAN)
- **Industry**: Financial Technology / Software Services
- **Entity Type**: Private Limited Company
- **State**: Maharashtra (State Code `27`)
- **PAN**: `AAPCA1111A` (Synthetic Test PAN)
- **GSTIN**: `27AAPCA1111A1Z1` (Synthetic Test GSTIN)
- **Primary Contact**: Aryan Sharma (`aryan@example.test`)
- **Financial Years**: Current FY 2025-26 & Prior FY 2024-25

### Company 2: Hitansh Fintech Pvt. Ltd. (HITANSH)
- **Industry**: Financial Technology / SaaS
- **Entity Type**: Private Limited Company
- **State**: Maharashtra (State Code `27`)
- **PAN**: `AAHCH2222H` (Synthetic Test PAN)
- **GSTIN**: `27AAHCH2222H1Z2` (Synthetic Test GSTIN)
- **Primary Contact**: Hitansh Mehta (`hitansh@example.test`)
- **Financial Years**: Current FY 2025-26 & Prior FY 2024-25

---

## 2. Directory Layout

```
test_data/
├── __init__.py
├── README.md
├── companies.py              # Metadata definitions for Aryan & Hitansh
├── scenarios.py              # Clean vs. Stress scenario configurations
├── clients.py                # Client data loaders
├── transactions.py           # General ledger transaction loaders
├── bank_data.py              # Bank statement loaders
├── gst_data.py               # GSTR-2B / GST Portal loaders
├── trial_balance.py          # Trial balance definitions
├── findings.py               # Audit findings fixtures
├── working_papers.py         # Working paper fixtures
├── checklists.py             # Statutory checklist fixtures
├── generator.py              # Deterministic dataset builder
├── seed.py                   # Database seeder utility
├── aryan_fintech/            # Aryan Fintech test datasets
│   ├── company.json
│   ├── clients.csv
│   ├── transactions.csv
│   ├── sales_register.csv
│   ├── purchase_register.csv
│   ├── bank_statement.csv
│   ├── gst_portal.csv
│   ├── prior_year_transactions.csv
│   └── expected_results.json
└── hitansh_fintech/          # Hitansh Fintech test datasets
    ├── company.json
    ├── clients.csv
    ├── transactions.csv
    ├── sales_register.csv
    ├── purchase_register.csv
    ├── bank_statement.csv
    ├── gst_portal.csv
    ├── prior_year_transactions.csv
    └── expected_results.json
```

---

## 3. Production Isolation Guarantees

1. **Zero Fabrication**: Production services derive results exclusively from database records and uploaded files. When data is missing, calculations report `MISSING` or `NOT_AVAILABLE`.
2. **No Production Imports**: Production code (`backend/app/*`) does not import `test_data`.
3. **Cross-Company Isolation**: Transactions, findings, working papers, BRS, GST, and AI queries for Aryan and Hitansh cannot be accessed or linked across company boundaries.
