"""
Standard Statutory Audit Checklist Templates
FinAuditPro - Intelligent Offline Auditing Platform

Covers Companies Act 2013, CARO 2020, Tax Audit (Form 3CD), and GST Statutory Audit requirements.
"""

STANDARD_CHECKLIST_ITEMS = [
    # 1. Companies Act 2013 & CARO 2020
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-01",
        "question": "Whether the company is maintaining proper records showing full particulars of Property, Plant and Equipment (PPE)?",
        "guidance": "Clause (i)(a) of CARO 2020. Verify Fixed Asset Register with physical verification records and title deeds."
    },
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-02",
        "question": "Whether physical verification of inventory has been conducted at reasonable intervals by the management?",
        "guidance": "Clause (ii)(a) of CARO 2020. Confirm coverage, frequency, and discrepancy treatment (>10% in aggregate)."
    },
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-03",
        "question": "Whether the company has maintained audit trail (edit log) feature throughout the financial year without tampering?",
        "guidance": "Section 143(3)(j) read with Rule 11(g) of Companies (Audit and Auditors) Rules 2014."
    },
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-04",
        "question": "Whether quarterly returns or statements submitted by the company to banks/FIs for sanctioned working capital limits are in agreement with books of account?",
        "guidance": "Clause (ii)(b) of CARO 2020. Reconcile book stock/debtors with monthly/quarterly DP statements."
    },
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-05",
        "question": "Whether the company has made investments in, provided guarantee or security or granted any loans/advances to related parties in accordance with Section 185/186?",
        "guidance": "Clause (iii) and (iv) of CARO 2020. Check loan register, board resolutions, and terms prejudicial to company interest."
    },
    {
        "category": "Companies Act 2013 & CARO 2020",
        "item_code": "CARO-06",
        "question": "Whether there is an internal audit system commensurate with the size and nature of its business?",
        "guidance": "Clause (xiv) of CARO 2020 read with Section 138 of Companies Act 2013. Review internal audit reports and follow-up."
    },

    # 2. Tax Audit (Form 3CD)
    {
        "category": "Tax Audit (Form 3CD)",
        "item_code": "3CD-21D",
        "question": "Whether any payment was made in cash exceeding ₹10,000 in contravention of Section 40A(3) / 40A(3A)?",
        "guidance": "Clause 21(d) of Form 3CD. Cross-verify with FinAuditPro Deterministic Cash Anomaly Engine."
    },
    {
        "category": "Tax Audit (Form 3CD)",
        "item_code": "3CD-31",
        "question": "Particulars of each loan, deposit, or specified sum exceeding ₹20,000 received or repaid otherwise than by banking channels u/s 269SS/269T, or cash receipts >= ₹2,00,000 u/s 269ST?",
        "guidance": "Clause 31 of Form 3CD. Verify Section 269SS, 269T, and 269ST exceptions."
    },
    {
        "category": "Tax Audit (Form 3CD)",
        "item_code": "3CD-34",
        "question": "Whether the assessee is required to deduct or collect tax (TDS/TCS) as per Chapter XVII-B and whether deposited within due date?",
        "guidance": "Clause 34 of Form 3CD. Verify Form 26Q/27Q reconciliations with General Ledger TDS provision accounts."
    },
    {
        "category": "Tax Audit (Form 3CD)",
        "item_code": "3CD-26H",
        "question": "Whether any sum payable to micro or small enterprises remained unpaid beyond the time limit specified under Section 15 of MSMED Act 2006 (Section 43B(h))?",
        "guidance": "Clause 26/Clause 22 of Form 3CD read with Section 43B(h). Verify MSME registration status and aging."
    },
    {
        "category": "Tax Audit (Form 3CD)",
        "item_code": "3CD-44",
        "question": "Break-up of total expenditure of entities registered and not registered under the GST?",
        "guidance": "Clause 44 of Form 3CD. Reconcile GSTR-9 / GSTR-3B total expenditure with Trial Balance expense ledgers."
    },

    # 3. GST Statutory Compliance
    {
        "category": "GST Statutory Compliance",
        "item_code": "GST-01",
        "question": "Whether Input Tax Credit (ITC) availed in GSTR-3B matches GSTR-2B auto-drafted statements and is eligible under Section 16 & Section 17(5)?",
        "guidance": "Verify against FinAuditPro GST Reconciliation Engine exceptions (mismatches, blocked credits, unreflected invoices)."
    },
    {
        "category": "GST Statutory Compliance",
        "item_code": "GST-02",
        "question": "Whether turnover reported in GSTR-1 matches General Ledger Sales Revenue accounts and outward supply tax rates?",
        "guidance": "Cross-verify with Sales Register Reconciliation and ensure appropriate HSN/SAC code classification."
    },

    # 4. Financial Statements & Closing
    {
        "category": "Financial Statements & Closing",
        "item_code": "FS-01",
        "question": "Whether revenue recognition complies with AS-9 / Ind AS 115 and cut-off procedures have been verified for year-end transactions?",
        "guidance": "Perform 15-day pre and post balance sheet date sales/purchase cut-off testing."
    },
    {
        "category": "Financial Statements & Closing",
        "item_code": "FS-02",
        "question": "Whether Bank Reconciliation Statements (BRS) have been prepared for all active bank accounts and old unpresented items reviewed?",
        "guidance": "Cross-verify with FinAuditPro BRS Engine for unpresented cheques > 90 days and stale entries."
    }
]
