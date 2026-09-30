import re
from typing import List, Dict, Any, Optional

class LocalAIAuditAssistant:
    """Local, offline AI assistant providing natural language explanations,
    audit notes, intelligent querying, and checklist suggestions."""

    def __init__(self, engagement_data: Dict[str, Any], transactions: List[Dict[str, Any]], findings: List[Dict[str, Any]]):
        self.engagement = engagement_data
        self.transactions = transactions
        self.findings = findings

    def generate_audit_summary_narrative(self) -> Dict[str, Any]:
        """Generates an executive summary narrative for the audit report."""
        total_tx = len(self.transactions)
        total_debit = sum(float(t.get('debit') or 0.0) for t in self.transactions)
        total_credit = sum(float(t.get('credit') or 0.0) for t in self.transactions)

        critical_findings = [f for f in self.findings if f.get('severity') == 'CRITICAL']
        high_findings = [f for f in self.findings if f.get('severity') == 'HIGH']
        medium_findings = [f for f in self.findings if f.get('severity') == 'MEDIUM']

        avg_risk = 0.0
        if self.findings:
            avg_risk = round(sum(float(f.get('risk_score') or 0) for f in self.findings) / len(self.findings), 2)

        risk_category = "Low"
        if len(critical_findings) > 0 or avg_risk >= 7.5:
            risk_category = "High"
        elif len(high_findings) > 2 or avg_risk >= 5.5:
            risk_category = "Medium"

        narrative = f"""
EXECUTIVE AUDIT SUMMARY & AI RISK OBSERVATIONS:
Engagement: {self.engagement.get('title', 'Annual Audit')} | FY: {self.engagement.get('financial_year', '2024-25')}

1. Scope & Scale:
   The audit engine evaluated {total_tx:,} transactions representing total debit turnover of ₹{total_debit:,.2f} and credit turnover of ₹{total_credit:,.2f}.

2. Risk Profile:
   The overall risk rating is assessed as [{risk_category.upper()}]. A total of {len(self.findings)} exception(s) were flagged:
   - Critical Severity: {len(critical_findings)} items
   - High Severity: {len(high_findings)} items
   - Medium Severity: {len(medium_findings)} items
   - Mean Anomaly Score: {avg_risk}/10

3. Key Risk Focus Areas:
"""
        if critical_findings:
            narrative += "   * CRITICAL MATTERS: Urgent review required for statutory violations (Section 40A(3) / 269ST) and ledger imbalances.\n"
        if high_findings:
            narrative += "   * HIGH RISK: Duplicate voucher entries and invalid GSTIN formats that threaten Input Tax Credit eligibility.\n"
        if not critical_findings and not high_findings:
            narrative += "   * General financial records exhibit standard compliance with minor documentation gaps.\n"

        narrative += f"""
4. Recommended Auditor Procedures:
   - Perform 100% substantive verification on all {len(critical_findings) + len(high_findings)} Critical/High exceptions.
   - Issue Management Letter observations for missing voucher narrations.
   - Reconcile GSTR-2B with Purchase Register before filing Tax Audit Form 3CD.
"""
        return {
            "narrative": narrative.strip(),
            "risk_category": risk_category,
            "average_risk_score": avg_risk,
            "total_exceptions": len(self.findings),
            "critical_count": len(critical_findings),
            "high_count": len(high_findings)
        }

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Answers auditor natural language questions against the loaded transactions and findings."""
        q = query.lower()
        response_text = ""
        evidence_items = []

        # 1. Cash / 40A(3) / 269ST queries
        if "cash" in q or "40a" in q or "269" in q:
            cash_tx = [t for t in self.transactions if 'cash' in str(t.get('ledger') or '').lower() or 'cash' in str(t.get('description') or '').lower()]
            total_cash = sum(float(t.get('amount') or t.get('debit') or 0.0) for t in cash_tx)
            large_cash = [t for t in cash_tx if float(t.get('amount') or t.get('debit') or 0.0) > 10000]

            response_text = f"Identified {len(cash_tx)} cash transaction(s) aggregating to ₹{total_cash:,.2f}.\n"
            if large_cash:
                response_text += f"There are {len(large_cash)} cash payment(s) exceeding the ₹10,000 threshold under Section 40A(3). These require review under Clause 21(d) of Form 3CD.\n"
                for t in large_cash[:5]:
                    amt = float(t.get('amount') or t.get('debit') or 0.0)
                    evidence_items.append({
                        "date": t.get('date'),
                        "voucher": t.get('voucher_no'),
                        "party": t.get('party_name'),
                        "amount": f"₹{amt:,.2f}",
                        "narration": t.get('description')
                    })
            else:
                response_text += "No individual cash payment exceeded the statutory ₹10,000 threshold."

        # 2. GST / Tax / 2B queries
        elif "gst" in q or "itc" in q or "tax" in q or "gstin" in q:
            gst_findings = [f for f in self.findings if "GST" in f.get('finding_code', '') or "GSTIN" in f.get('title', '')]
            response_text = f"Found {len(gst_findings)} GST-related audit observation(s).\n"
            for f in gst_findings[:4]:
                response_text += f"- [{f.get('severity')}] {f.get('title')}: {f.get('description')}\n"
                evidence_items.append({
                    "finding_code": f.get('finding_code'),
                    "title": f.get('title'),
                    "severity": f.get('severity'),
                    "action": f.get('recommended_action')
                })

        # 3. Highest / Largest transactions
        elif "largest" in q or "highest" in q or "top" in q or "big" in q:
            sorted_tx = sorted(self.transactions, key=lambda t: float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0), reverse=True)
            top_5 = sorted_tx[:5]
            response_text = f"Top 5 highest value transactions in the ledger:\n"
            for idx, t in enumerate(top_5, 1):
                amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
                response_text += f"{idx}. Date: {t.get('date')} | Ledger: {t.get('ledger')} | Party: {t.get('party_name') or 'N/A'} | Amount: ₹{amt:,.2f} (Voucher: {t.get('voucher_no')})\n"
                evidence_items.append({
                    "voucher": t.get('voucher_no'),
                    "date": t.get('date'),
                    "party": t.get('party_name'),
                    "ledger": t.get('ledger'),
                    "amount": f"₹{amt:,.2f}"
                })

        # 4. Critical / High risk findings
        elif "critical" in q or "high" in q or "risk" in q or "finding" in q or "anomal" in q:
            crit = [f for f in self.findings if f.get('severity') in ['CRITICAL', 'HIGH']]
            response_text = f"There are {len(crit)} Critical/High audit findings requiring immediate attention:\n"
            for f in crit:
                response_text += f"- [{f.get('severity')}] {f.get('title')} (Risk: {f.get('risk_score')}/10)\n  Reason: {f.get('reason')}\n"
                evidence_items.append({
                    "code": f.get('finding_code'),
                    "title": f.get('title'),
                    "severity": f.get('severity'),
                    "recommended_action": f.get('recommended_action')
                })

        # 5. Benford / Statistical / Outliers
        elif "benford" in q or "outlier" in q or "ml" in q:
            stat_findings = [f for f in self.findings if f.get('engine_type') == 'STATISTICAL_ML']
            response_text = f"Statistical & Machine Learning Engine identified {len(stat_findings)} outlier observation(s).\n"
            for f in stat_findings:
                response_text += f"- {f.get('title')}\n  Details: {f.get('description')}\n"
                evidence_items.append({
                    "title": f.get('title'),
                    "rule": f.get('rule_used'),
                    "action": f.get('recommended_action')
                })

        # 6. Default / General overview
        else:
            total_debit = sum(float(t.get('debit') or 0.0) for t in self.transactions)
            total_credit = sum(float(t.get('credit') or 0.0) for t in self.transactions)
            response_text = f"Audit Assistant Overview for '{self.engagement.get('title', 'Engagement')}':\n"
            response_text += f"- Total Transactions: {len(self.transactions)}\n"
            response_text += f"- Total Turnover: ₹{total_debit:,.2f} Dr / ₹{total_credit:,.2f} Cr\n"
            response_text += f"- Active Audit Findings: {len(self.findings)}\n"
            response_text += "You can ask me specific questions such as:\n"
            response_text += "  • 'Show large cash transactions above Section 40A(3) limit'\n"
            response_text += "  • 'What are the critical risks in this engagement?'\n"
            response_text += "  • 'What are the top 5 highest value vouchers?'\n"
            response_text += "  • 'Are there any GSTIN format or ITC matching issues?'\n"
            response_text += "  • 'Explain the Benford Law or ML outlier results'\n"

        return {
            "query": query,
            "response": response_text.strip(),
            "evidence": evidence_items
        }

    def explain_finding_in_depth(self, finding_id: int) -> Dict[str, Any]:
        """Provides an extensive CA-oriented explanation of a specific finding."""
        finding = next((f for f in self.findings if f.get('id') == finding_id or str(f.get('id')) == str(finding_id)), None)
        if not finding:
            return {"error": "Finding not found"}

        code = finding.get('finding_code', '')
        title = finding.get('title', '')
        severity = finding.get('severity', 'MEDIUM')
        rule = finding.get('rule_used', 'General Auditing Standard')

        explanation = f"""
AUDIT MEMORANDUM & WORKING PAPER NOTE:
Finding Reference: {code} | Severity: {severity}
Title: {title}

1. Accounting & Legal Framework:
   This exception was identified based on '{rule}'. Under Indian regulatory standards (ICAI Guidance Notes, Income Tax Act 1961, and Companies Act 2013), this matter poses statutory compliance and financial statement misstatement risk.

2. Evidence & Fact Summary:
   - Expected Treatment: {finding.get('expected_value', 'Standard accounting practice')}
   - Actual Condition: {finding.get('actual_value', 'Non-conforming ledger entry')}
   - Quantified Discrepancy: {finding.get('difference', 'N/A')}

3. Substantive Audit Impact:
   {finding.get('ai_explanation', 'Auditor review required to confirm tax and reporting consequences.')}

4. Suggested Working Paper Documentation:
   - Auditor Action: {finding.get('recommended_action', 'Examine supporting documents')}
   - Recommended WP Reference: WP-{code.replace('-', '_')}
   - Form 3CD / CARO 2020 Clause: Relevant clause documentation in permanent audit file.
"""
        return {
            "finding_id": finding_id,
            "formatted_memo": explanation.strip(),
            "rule": rule,
            "severity": severity,
            "recommended_action": finding.get('recommended_action')
        }
