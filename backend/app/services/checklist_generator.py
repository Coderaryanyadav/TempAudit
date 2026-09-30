import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_connection

CHECKLIST_CATEGORIES = [
    "Planning",
    "Internal Controls",
    "Cash & Bank",
    "Receivables",
    "Payables",
    "Inventory",
    "Fixed Assets",
    "Revenue",
    "Expenses",
    "Loans",
    "Related Parties",
    "Payroll",
    "Tax/GST",
    "Financial Statements",
    "Closing Procedures"
]

CHECKLIST_STATUSES = [
    "Not Started",
    "In Progress",
    "Completed",
    "Not Applicable",
    "Requires Review"
]

# Standard procedures matrix across all 15 audit categories
STANDARD_PROCEDURE_TEMPLATES = [
    # 1. Planning
    {
        "category": "Planning",
        "code_prefix": "PLN",
        "question": "Obtain signed Engagement Letter and verify independence under Code of Ethics (SA 210 / SA 220).",
        "guidance": "Confirm terms of audit engagement, objective, scope, and auditor responsibilities.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": []
    },
    {
        "category": "Planning",
        "code_prefix": "PLN",
        "question": "Establish overall audit strategy, scope, materiality threshold, and performance materiality (SA 300 / SA 320).",
        "guidance": "Document quantitative materiality benchmark (e.g., 0.5% - 2% of revenue or 1% - 5% of profit before tax).",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": []
    },
    {
        "category": "Planning",
        "code_prefix": "PLN",
        "question": "Inquire with predecessor auditor under Clause (8) of Part I of First Schedule to CA Act, 1949.",
        "guidance": "Verify written communication sent to previous auditor before accepting engagement.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": []
    },

    # 2. Internal Controls
    {
        "category": "Internal Controls",
        "code_prefix": "IC",
        "question": "Evaluate design and operating effectiveness of Internal Financial Controls over Financial Reporting (ICFR u/s 143(3)(i)).",
        "guidance": "Test segregation of duties, ERP access controls, and management authorization matrices.",
        "client_types": ["Private Limited", "Public Limited", "Listed Company"],
        "audit_types": ["Statutory Audit", "Internal Audit"],
        "modules": ["General Ledger"]
    },
    {
        "category": "Internal Controls",
        "code_prefix": "IC",
        "question": "Verify Audit Trail (Edit Log) feature is enabled throughout the financial year without tampering (Rule 11(g)).",
        "guidance": "Verify accounting software preserves log of every change, timestamp, and user who updated transaction.",
        "client_types": ["Private Limited", "Public Limited", "Listed Company"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Audit Trail Log", "General Ledger"]
    },

    # 3. Cash & Bank
    {
        "category": "Cash & Bank",
        "code_prefix": "BNK",
        "question": "Perform surprise physical cash count at year-end and reconcile with Cash Book closing balance.",
        "guidance": "Obtain signed cash count certificate from management custodian as of closing date.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["General Ledger"]
    },
    {
        "category": "Cash & Bank",
        "code_prefix": "BNK",
        "question": "Obtain direct external Bank Confirmations under SA 505 for all operative and dormant bank accounts.",
        "guidance": "Independent balance confirmation for current, savings, OD, CC, and term deposit accounts.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["Bank Reconciliation"]
    },
    {
        "category": "Cash & Bank",
        "code_prefix": "BNK",
        "question": "Verify Bank Reconciliation Statements (BRS) and examine unpresented cheques older than 90 days / uncredited deposits.",
        "guidance": "Inspect stale cheques for reversal or re-issuance and investigate timing differences.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["Bank Reconciliation"]
    },

    # 4. Receivables
    {
        "category": "Receivables",
        "code_prefix": "REC",
        "question": "Circulate external balance confirmation requests to major trade debtors under SA 505.",
        "guidance": "Select sample covering top 80% debtor exposure plus random sampling of disputed balances.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["General Ledger", "Sales / Purchase Reconciliation"]
    },
    {
        "category": "Receivables",
        "code_prefix": "REC",
        "question": "Review debtors ageing schedule and assess Expected Credit Loss (ECL) / provision for doubtful debts.",
        "guidance": "Schedule III disclosure of ageing (> 6 months, > 1 year, > 2 years, > 3 years, undisputed vs disputed).",
        "client_types": ["Private Limited", "Public Limited", "LLP"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["Financial Statements", "General Ledger"]
    },

    # 5. Payables
    {
        "category": "Payables",
        "code_prefix": "PAY",
        "question": "Perform MSME dues verification and identify payments delayed beyond 45 days (MSMED Act 2006 / Sec 43B(h)).",
        "guidance": "Verify MSME registration certificates and calculate interest liability u/s 16 MSMED Act.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["General Ledger", "Tax/GST"]
    },
    {
        "category": "Payables",
        "code_prefix": "PAY",
        "question": "Reconcile vendor statement of accounts with purchase ledger and examine unrecorded liabilities post year-end.",
        "guidance": "Perform search for unrecorded liabilities by inspecting April payments for previous year services.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["Sales / Purchase Reconciliation", "General Ledger"]
    },

    # 6. Inventory
    {
        "category": "Inventory",
        "code_prefix": "INV",
        "question": "Attend physical stock count as an observer at year-end and perform test counts (SA 501 / CARO Clause (ii)).",
        "guidance": "Verify procedure for identifying damaged, slow-moving, and obsolete inventory items.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Internal Audit"],
        "modules": ["Inventory Audit"]
    },
    {
        "category": "Inventory",
        "code_prefix": "INV",
        "question": "Verify inventory valuation methodology complies with AS-2 / Ind AS-2 (Lower of Cost and Net Realizable Value).",
        "guidance": "Test costing formula (FIFO / Weighted Average) including absorption of direct overheads.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["Financial Statements"]
    },

    # 7. Fixed Assets
    {
        "category": "Fixed Assets",
        "code_prefix": "FA",
        "question": "Verify Fixed Asset Register (FAR) is updated with full quantitative particulars and location details (CARO Clause (i)).",
        "guidance": "Check title deeds of all immovable properties shown in financial statements are held in company name.",
        "client_types": ["Private Limited", "Public Limited", "LLP"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Financial Statements"]
    },
    {
        "category": "Fixed Assets",
        "code_prefix": "FA",
        "question": "Verify depreciation computation matches useful lives prescribed under Schedule II of Companies Act, 2013.",
        "guidance": "Cross-check depreciation rates for tax audit (Income Tax Rule 5, Appendix I).",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["General Ledger"]
    },

    # 8. Revenue
    {
        "category": "Revenue",
        "code_prefix": "REV",
        "question": "Perform revenue cut-off procedures for sales transactions 5 days before and 5 days after balance sheet date.",
        "guidance": "Verify risk and rewards / control of goods transferred before recognizing revenue (AS-9 / Ind AS-115).",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["General Ledger", "Sales / Purchase Reconciliation"]
    },
    {
        "category": "Revenue",
        "code_prefix": "REV",
        "question": "Reconcile total revenue recognized in Books with GSTR-1, GSTR-3B, and Income Tax Annual Information Statement (AIS).",
        "guidance": "Explain turnover differences, advance receipts, unbilled revenue, and credit note adjustments.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["GST Reconciliation", "General Ledger"]
    },

    # 9. Expenses
    {
        "category": "Expenses",
        "code_prefix": "EXP",
        "question": "Test expense vouchers for Section 40A(3) cash payments exceeding ₹10,000 per person per day.",
        "guidance": "Cross-verify with FinAuditPro Deterministic Rule Engine exceptions under Clause 21(d) Form 3CD.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["Statutory & Tax Rules", "General Ledger"]
    },
    {
        "category": "Expenses",
        "code_prefix": "EXP",
        "question": "Verify statutory Tax Deducted at Source (TDS/TCS) deduction, deposit, and return filing (Section 40(a)(ia)).",
        "guidance": "Confirm TDS on contractor payments (194C), professional fees (194J), rent (194I), and interest (194A).",
        "client_types": ["ALL"],
        "audit_types": ["Tax Audit", "Statutory Audit"],
        "modules": ["Tax/GST", "General Ledger"]
    },

    # 10. Loans
    {
        "category": "Loans",
        "code_prefix": "LON",
        "question": "Verify compliance with Section 269SS and Section 269T regarding acceptance and repayment of loans/deposits.",
        "guidance": "Verify no loan or deposit of ₹20,000 or more was accepted or repaid otherwise than by account payee cheque/electronic mode.",
        "client_types": ["ALL"],
        "audit_types": ["Tax Audit", "Statutory Audit"],
        "modules": ["Statutory & Tax Rules", "General Ledger"]
    },
    {
        "category": "Loans",
        "code_prefix": "LON",
        "question": "Verify compliance with Section 185 and Section 186 of Companies Act, 2013 regarding loans to directors and investments.",
        "guidance": "Check registers maintained under Section 186(9) in Form MBP-2.",
        "client_types": ["Private Limited", "Public Limited"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Financial Statements"]
    },

    # 11. Related Parties
    {
        "category": "Related Parties",
        "code_prefix": "RP",
        "question": "Obtain comprehensive list of related parties and directors' interest disclosures (Form MBP-1 / Section 184).",
        "guidance": "Cross-check register of contracts in which directors are interested maintained u/s 189 in Form MBP-4.",
        "client_types": ["Private Limited", "Public Limited", "LLP"],
        "audit_types": ["Statutory Audit"],
        "modules": ["General Ledger", "Financial Statements"]
    },
    {
        "category": "Related Parties",
        "code_prefix": "RP",
        "question": "Examine related party transactions for Arm's Length Pricing and Board/Audit Committee approvals (Section 188 / AS-18).",
        "guidance": "Verify transfer pricing documentation where international or specified domestic transactions exist u/s 92E.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["General Ledger"]
    },

    # 12. Payroll
    {
        "category": "Payroll",
        "code_prefix": "PAYR",
        "question": "Verify monthly payroll register, PF / ESI contribution deposits within statutory due dates (Section 36(1)(va)).",
        "guidance": "Verify employees' contribution to welfare funds deposited on or before the due date specified in relevant Acts.",
        "client_types": ["ALL"],
        "audit_types": ["Tax Audit", "Statutory Audit"],
        "modules": ["General Ledger", "Tax/GST"]
    },
    {
        "category": "Payroll",
        "code_prefix": "PAYR",
        "question": "Verify provision for gratuity, leave encashment, and bonus based on actuarial valuation (AS-15 / Ind AS-19).",
        "guidance": "Inspect actuarial valuation report and verify mathematical consistency with financial statement provisions.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Financial Statements"]
    },

    # 13. Tax/GST
    {
        "category": "Tax/GST",
        "code_prefix": "TAX",
        "question": "Reconcile Input Tax Credit (ITC) claimed in GSTR-3B with GSTR-2B under Section 16(2)(aa) of CGST Act.",
        "guidance": "Ensure no ineligible ITC is claimed for restricted items under Section 17(5) (motor vehicles, food/catering, personal use).",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["GST Reconciliation"]
    },
    {
        "category": "Tax/GST",
        "code_prefix": "TAX",
        "question": "Verify advance tax payment instalments and calculation of interest u/s 234B and 234C of Income Tax Act.",
        "guidance": "Confirm quarterly advance tax challans paid by 15th June, 15th Sep, 15th Dec, and 15th March.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit", "Tax Audit"],
        "modules": ["General Ledger"]
    },

    # 14. Financial Statements
    {
        "category": "Financial Statements",
        "code_prefix": "FS",
        "question": "Verify Balance Sheet, Statement of Profit & Loss, and Notes comply with Schedule III of Companies Act, 2013.",
        "guidance": "Check mandatory regulatory ratios disclosures and aging schedules for trade payables, receivables, CWIP, and intangibles.",
        "client_types": ["Private Limited", "Public Limited"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Financial Statements", "Trial Balance Analysis"]
    },
    {
        "category": "Financial Statements",
        "code_prefix": "FS",
        "question": "Review contingent liabilities, commitments, capital contracts, and pending litigations (AS-29 / Ind AS-37).",
        "guidance": "Obtain legal letter / confirmation from legal counsels representing client in tax/civil disputes.",
        "client_types": ["ALL"],
        "audit_types": ["Statutory Audit"],
        "modules": ["Financial Statements"]
    },

    # 15. Closing Procedures
    {
        "category": "Closing Procedures",
        "code_prefix": "CLS",
        "question": "Perform review of Subsequent Events occurring between Balance Sheet date and Audit Report date (SA 560).",
        "guidance": "Identify adjusting events (providing evidence of conditions existing at BS date) and non-adjusting material events.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["General Ledger"]
    },
    {
        "category": "Closing Procedures",
        "code_prefix": "CLS",
        "question": "Obtain signed Management Representation Letter (MRL) covering all material balance sheet heads and disclosures (SA 580).",
        "guidance": "Ensure MRL is dated on or immediately prior to the date of the auditor's report.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": []
    },
    {
        "category": "Closing Procedures",
        "code_prefix": "CLS",
        "question": "Verify Going Concern assumption under SA 570 and evaluate operating losses / net current liability position.",
        "guidance": "Assess management plans, cash flow forecasts for next 12 months, and bank sanction letter renewals.",
        "client_types": ["ALL"],
        "audit_types": ["ALL"],
        "modules": ["Financial Statements", "YoY Comparison"]
    }
]

class ChecklistGenerator:
    """
    Intelligent Checklist Generator for FinAuditPro.
    Dynamically generates audit checklists across 15 standard categories tailored to:
    - Client Type
    - Audit Type
    - Financial Year
    - Active Subsystem Modules
    - Risk & Findings Exceptions
    """

    @classmethod
    def generate_checklist(
        cls,
        engagement_id: int,
        client_type: Optional[str] = None,
        audit_type: Optional[str] = None,
        financial_year: Optional[str] = None,
        selected_modules: Optional[List[str]] = None,
        regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generates or refreshes the audit checklist for an engagement.
        Rules:
        - NEVER automatically sets items to 'Completed'.
        - Sets base items to 'Not Started'.
        - Sets risk-findings-linked items to 'Requires Review' with clear evidence.
        - Preserves existing auditor comments, assigned staff, and reviews if not regenerating from scratch.
        """
        conn = get_db_connection()
        eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        if not eng_row:
            conn.close()
            raise ValueError(f"Engagement #{engagement_id} not found.")

        eng = dict(eng_row)
        client_row = conn.execute("SELECT * FROM clients WHERE id = ?", (eng.get("client_id", 0),)).fetchone()
        client_dict = dict(client_row) if client_row else {}

        # Resolve parameters
        c_type = client_type or client_dict.get("client_type") or "Private Limited"
        a_type = audit_type or eng.get("audit_type") or "Statutory Audit"
        fy = financial_year or eng.get("financial_year") or "2024-25"
        sel_modules = selected_modules or []

        # Existing items
        existing_items = conn.execute(
            "SELECT * FROM audit_checklists WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchall()
        existing_by_code = {r["item_code"]: dict(r) for r in existing_items}

        if regenerate:
            # Delete non-custom items if full regenerate requested
            conn.execute(
                "DELETE FROM audit_checklists WHERE engagement_id = ? AND is_custom = 0",
                (engagement_id,)
            )

        now_str = datetime.now().isoformat()
        items_to_insert = []
        item_counter = {}

        # 1. Evaluate Standard Templates against Client Type, Audit Type & Modules
        for tmpl in STANDARD_PROCEDURE_TEMPLATES:
            # Check Client Type match
            if "ALL" not in tmpl["client_types"]:
                if not any(ct.lower() in c_type.lower() for ct in tmpl["client_types"]):
                    continue

            # Check Audit Type match
            if "ALL" not in tmpl["audit_types"]:
                if not any(at.lower() in a_type.lower() for at in tmpl["audit_types"]):
                    continue

            cat = tmpl["category"]
            prefix = tmpl["code_prefix"]
            item_counter[prefix] = item_counter.get(prefix, 0) + 1
            code = f"CHK-{prefix}-{item_counter[prefix]:02d}"

            # If already exists and not regenerating, preserve
            if code in existing_by_code and not regenerate:
                continue

            # Default status is 'Not Started'
            # Note: Do not automatically mark completed based on AI
            initial_status = "Not Started"

            # Check if relevant modules are active
            guidance_text = tmpl["guidance"]
            if tmpl["modules"]:
                guidance_text += f" (Relevant for: {', '.join(tmpl['modules'])})"

            items_to_insert.append({
                "category": cat,
                "item_code": code,
                "question": tmpl["question"],
                "guidance": guidance_text,
                "status": initial_status,
                "assigned_staff": eng.get("assigned_staff_id") or "Unassigned",
                "evidence": "",
                "comment": "",
                "due_date": eng.get("period_end") or f"{fy.split('-')[0]}-12-31",
                "completed_date": None,
                "is_custom": 0,
                "risk_finding_id": None
            })

        # 2. Risk Findings Integration:
        # Dynamically generate procedures for high-risk / critical audit findings detected in the engagement!
        finding_rows = conn.execute(
            "SELECT * FROM audit_findings WHERE engagement_id = ? ORDER BY risk_score DESC",
            (engagement_id,)
        ).fetchall()

        finding_counter = 0
        for f in finding_rows:
            f_dict = dict(f)
            sev = (f_dict.get("severity") or "MEDIUM").upper()
            score = float(f_dict.get("risk_score") or 0.0)
            finding_id = f_dict["id"]
            code_base = f_dict.get("finding_code") or f"FIND-{finding_id}"

            # Only generate checklist items for findings with risk score >= 5.0 or severity HIGH/CRITICAL
            if sev in ["CRITICAL", "HIGH"] or score >= 5.0:
                finding_counter += 1
                cat = cls._map_finding_to_checklist_category(f_dict)
                chk_code = f"CHK-RSK-{finding_counter:02d}"

                if chk_code in existing_by_code and not regenerate:
                    continue

                procedure_text = f"Substantive Verification: {f_dict.get('title')} ({code_base}) - Investigate and obtain management explanation."
                action_text = f_dict.get("recommended_action") or "Perform substantive verification and verify supporting documentation."
                guidance_text = f"Triggered by {f_dict.get('module')} Finding ({code_base}, Risk Score: {score}/10). Recommended Action: {action_text}"
                evidence_ref = f"Audit Finding: {code_base} | Discrepancy: {f_dict.get('difference') or 'Exception noted'}"

                # Mandatory rule: Risk-driven items enter as 'Requires Review' (NEVER Completed)
                items_to_insert.append({
                    "category": cat,
                    "item_code": chk_code,
                    "question": procedure_text,
                    "guidance": guidance_text,
                    "status": "Requires Review",
                    "assigned_staff": eng.get("assigned_staff_id") or "Audit Senior",
                    "evidence": evidence_ref,
                    "comment": f"Auto-linked from {f_dict.get('module')} exception: {f_dict.get('reason') or f_dict.get('title')}",
                    "due_date": eng.get("period_end") or f"{fy.split('-')[0]}-12-31",
                    "completed_date": None,
                    "is_custom": 0,
                    "risk_finding_id": finding_id
                })

        # Insert new items into database
        inserted_count = 0
        for item in items_to_insert:
            conn.execute("""
            INSERT INTO audit_checklists (
                engagement_id, category, item_code, question, guidance, status,
                assigned_staff, evidence, comment, due_date, completed_date,
                is_custom, risk_finding_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                engagement_id,
                item["category"],
                item["item_code"],
                item["question"],
                item["guidance"],
                item["status"],
                str(item["assigned_staff"] or ""),
                item["evidence"],
                item["comment"],
                item["due_date"],
                item["completed_date"],
                item["is_custom"],
                item["risk_finding_id"],
                now_str
            ))
            inserted_count += 1

        conn.commit()

        # Query total count and summary
        total_items = conn.execute(
            "SELECT COUNT(*) as c FROM audit_checklists WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchone()["c"]

        conn.close()

        return {
            "engagement_id": engagement_id,
            "client_type": c_type,
            "audit_type": a_type,
            "financial_year": fy,
            "total_items": total_items,
            "newly_generated": inserted_count,
            "risk_finding_procedures_count": finding_counter,
            "status": "success",
            "message": f"Audit Checklist generated with {total_items} procedures across all 15 audit categories."
        }

    @staticmethod
    def _map_finding_to_checklist_category(finding: Dict[str, Any]) -> str:
        """Maps an audit finding module and title to one of the 15 standard checklist categories."""
        mod = (finding.get("module") or "").lower()
        title = (finding.get("title") or "").lower()
        cat = (finding.get("category") or "").lower()

        if "gst" in mod or "gst" in title or "tax" in mod or "269st" in title or "40a" in title:
            return "Tax/GST"
        if "bank" in mod or "brs" in title or "cash" in title:
            return "Cash & Bank"
        if "inventory" in mod or "stock" in title:
            return "Inventory"
        if "receivable" in title or "debtor" in title or "customer" in title:
            return "Receivables"
        if "payable" in title or "creditor" in title or "vendor" in title:
            return "Payables"
        if "asset" in title or "depreciation" in title:
            return "Fixed Assets"
        if "sales" in title or "revenue" in title:
            return "Revenue"
        if "salary" in title or "payroll" in title or "wages" in title or "remuneration" in title:
            return "Payroll"
        if "loan" in title or "deposit" in title or "borrowing" in title:
            return "Loans"
        if "related" in title or "director" in title:
            return "Related Parties"
        if "trial balance" in mod or "suspense" in title or "imbalance" in title:
            return "Financial Statements"
        if "duplicate" in mod or "sequence" in mod:
            return "Internal Controls"
        if "yoy" in mod:
            return "Financial Statements"
        return "Expenses"

    @classmethod
    def get_checklist_summary(cls, engagement_id: int) -> Dict[str, Any]:
        """
        Returns structured metrics for the Checklist Dashboard:
        - Total procedures
        - Breakdown by category (all 15 categories)
        - Breakdown by status (Not Started, In Progress, Completed, Not Applicable, Requires Review)
        - Completion percentage
        """
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT * FROM audit_checklists WHERE engagement_id = ?",
            (engagement_id,)
        ).fetchall()
        conn.close()

        total = len(rows)
        by_status = {
            "Not Started": 0,
            "In Progress": 0,
            "Completed": 0,
            "Not Applicable": 0,
            "Requires Review": 0
        }
        by_category = {cat: 0 for cat in CHECKLIST_CATEGORIES}

        for r in rows:
            st = r["status"]
            # Handle legacy 'Pending' mapping
            if st == "Pending":
                st = "Not Started"
            elif st == "Complied":
                st = "Completed"
            elif st == "Exception":
                st = "Requires Review"

            if st in by_status:
                by_status[st] += 1
            else:
                by_status["Not Started"] += 1

            cat = r["category"]
            if cat in by_category:
                by_category[cat] += 1
            else:
                by_category[cat] = 1

        active_denominator = max(1, total - by_status["Not Applicable"])
        completion_pct = round((by_status["Completed"] / active_denominator) * 100, 1)

        return {
            "engagement_id": engagement_id,
            "total_items": total,
            "completed_count": by_status["Completed"],
            "not_started_count": by_status["Not Started"],
            "in_progress_count": by_status["In Progress"],
            "requires_review_count": by_status["Requires Review"],
            "not_applicable_count": by_status["Not Applicable"],
            "completion_percentage": completion_pct,
            "by_status": by_status,
            "by_category": by_category,
            "available_categories": CHECKLIST_CATEGORIES
        }
