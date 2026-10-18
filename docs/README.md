# TempAudit / FinAuditPro — Documentation Suite Index

This directory contains the production-grade documentation suite for **FinAuditPro**, organized according to the enterprise release standard.

---

## 📑 Production Documentation Index

| Ref | Document | Description | Target Audience |
| :--- | :--- | :--- | :--- |
| **00** | [Repository Inventory](production/00-repository-inventory.md) | File manifest, LOC analysis, route inventory, and security hygiene audit | Developers, Architects, Auditors |
| **01** | [Documentation Gap Analysis](production/01-documentation-gap-analysis.md) | Pre-production gap assessment, missing documentation remediation | Project Managers, QA Leads |
| **02** | [Product Overview](production/02-product-overview.md) | Strategic product brief, ICAI standard alignment, and enterprise value proposition | CA Partners, Technical Buyers |
| **03** | [User Manual](production/03-user-manual.md) | Complete 16-screen auditor desktop manual from setup to master PDF generation | Audit Seniors, Articles, Reviewers |
| **05** | [Technical Architecture](production/05-technical-architecture.md) | 3-tier hybrid engine, SQLite schema, offline AI models, and data security | Software Architects, InfoSec Teams |
| **08** | [Audit Rules & Calculations](production/08-audit-rules-and-calculations.md) | Income Tax Act, Form 3CD clauses, and GST statutory reconciliation mathematics | Tax Reviewers, Forensic Auditors |
| **17** | [Verification & Test Evidence](production/17-verification-and-test-evidence.md) | Real browser Playwright test logs, 21-screen test results, and test suite matrix | QA Leads, Security Auditors |
| **18** | [Release Readiness Matrix](production/18-release-readiness-matrix.md) | Production checklist, launch gating, deployment guidelines, and release sign-off | Release Managers, Practice Leaders |

---

## 🛠️ Automated Browser Test Suite

Automated verification tests are maintained in `scripts/`:

1. `scripts/test_real_browser_auth.py`: Tests real browser session restore, tab persistence, and token security.
2. `scripts/test_real_browser_full_journey.py`: Tests clean rendering of all 21 UI views and tabs in real Chromium.
3. `scripts/test_real_browser_deep_input.py`: Performs full interactive end-to-end workflow (Login → Client Master → Engagement → Data Import & Ingestion → Finding Scan → Local AI Chat → Master PDF Report → Hard Page Reload → Logout).
