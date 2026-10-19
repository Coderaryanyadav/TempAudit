"""
Local AI Audit Assistant Engine (100% Offline)
FinAuditPro - Intelligent Offline Auditing Platform

Architecture:
User question -> Intent detection -> Retrieve relevant local data -> Deterministic calculations -> Local AI response synthesis -> Evidence-based answer with inspectable source transactions.

Zero-Hallucination Constraint:
- Calculates all numerical metrics using the audit engine first.
- Strictly bases explanations on available database records and deterministic calculations.
- Always provides the mandatory disclaimer and inspectable source transactions.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from backend.app.database import get_db_connection
from backend.app.services.yoy_comparison_engine import run_yoy_comparison
from backend.app.services.anomaly_detection_engine import detect_all_anomalies
from backend.app.services.financial_statement_analysis_engine import run_financial_statement_analysis
from backend.app.services.trial_balance_analyzer import analyze_trial_balance

MANDATORY_DISCLAIMER = "AI-generated assistance. Verify findings against source records before making audit decisions."

def detect_intent(query: str) -> str:
    """
    Identifies the semantic audit intent from the user query using robust pattern matching.
    """
    q = (query or "").strip().lower()
    
    # 1. Why was transaction flagged / explain transaction
    if re.search(r'\b(why|explain|reason)\b.*\b(flagged|flag|voucher|transaction|invoice|entry|item)\b', q) or \
       re.search(r'\b(voucher|v-\d+|inv-\d+|tx-\d+)\b', q) or \
       "why is" in q or "why was" in q:
        return "EXPLAIN_FLAGGED_TRANSACTION"
    
    # 2. Unusual transactions / Anomalies / Outliers
    if re.search(r'\b(unusual|anomal|anomalies|outlier|outliers|suspicious|flagged|irregular|abnormal)\b', q) or \
       "high risk voucher" in q or "unusual transaction" in q or "anomaly detection" in q:
        return "UNUSUAL_TRANSACTIONS"
    
    # 3. Summarize financial movement / Financial health
    if re.search(r'\b(financial movement|financial health|performance|p&l|balance sheet|profitability|financial summary)\b', q) or \
       "summarize this client" in q or "client's financial" in q:
        return "FINANCIAL_MOVEMENT"
    
    # 4. Year-on-Year changes / Variances
    if re.search(r'\b(year-on-year|year on year|yoy|annual change|varianc|growth|largest change|biggest change)\b', q) or \
       "which ledgers have the largest" in q or "compare years" in q or "largest movements" in q or "yoy movement" in q:
        return "YOY_CHANGES"
    
    # 5. Bank reconciliation / Unmatched bank transactions
    if re.search(r'\b(bank|brs|unmatched bank|unpresented|cheque|deposit in transit|bank charge)\b', q) or \
       "bank reconciliation" in q or "missing in bank" in q or "missing in books" in q:
        return "UNMATCHED_BANK"
    
    # 6. Summarize audit exceptions / Major findings
    if re.search(r'\b(summarize|summary|overview|breakdown)\b.*\b(exception|exceptions|finding|findings|risk|critical)\b', q) or \
       "major audit exceptions" in q or "key findings" in q or "audit overview" in q:
        return "SUMMARIZE_EXCEPTIONS"
    
    # 7. Accounts requiring review / High risk ledgers
    if re.search(r'\b(which accounts|accounts require|ledgers require|accounts need|ledgers need|high risk account|suspense|abnormal balance)\b', q) or \
       "require review" in q or "needs review" in q or "which accounts" in q:
        return "ACCOUNTS_REQUIRE_REVIEW"
    
    # 8. Explain reconciliation difference / GST / Sales-Purchase
    if re.search(r'\b(reconciliation difference|gst mismatch|sales purchase difference|2b mismatch|gstr|reconciliation exception)\b', q) or \
       "explain this reconciliation" in q or "tax difference" in q:
        return "EXPLAIN_RECONCILIATION"
    
    # 9. Create audit observation / Working paper note
    if re.search(r'\b(create|draft|write|generate)\b.*\b(observation|working paper|note|memo|memorandum|finding)\b', q) or \
       "audit observation" in q or "working paper note" in q:
        return "CREATE_AUDIT_OBSERVATION"
    
    # 10. Cash limit / Section 40A(3) / 269ST
    if "40a" in q or "269st" in q or "cash" in q:
        return "CASH_STATUTORY_LIMITS"
    
    # 11. Top / Largest transactions
    if re.search(r'\b(largest|highest|top|biggest)\b.*\b(transaction|voucher|payment|receipt|entry)\b', q):
        return "LARGEST_TRANSACTIONS"

    # 12. Help / Capabilities / Greeting
    if re.search(r'\b(hi|hello|hey|help|guide|assist|capabilities|what can you do|who are you)\b', q):
        return "GENERAL_AUDIT_QUERY"
    
    return "GENERAL_AUDIT_QUERY"

class LocalAIAssistantEngine:
    """
    Offline Local AI Assistant for FinAuditPro.
    Evaluates queries deterministically, aggregates local evidence, and synthesizes CA-grade audit responses.
    """

    def __init__(self, engagement_id: int):
        self.engagement_id = engagement_id
        self._load_base_data()

    def _load_base_data(self):
        conn = get_db_connection()
        eng = conn.execute("SELECT * FROM engagements WHERE id = ?", (self.engagement_id,)).fetchone()
        if not eng:
            conn.close()
            raise ValueError(f"Engagement {self.engagement_id} not found")
        self.engagement = dict(eng)
        
        # Load Client
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (self.engagement["client_id"],)).fetchone()
        self.client_info = dict(client) if client else {}

        # Load Transactions
        tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ? ORDER BY id ASC", (self.engagement_id,)).fetchall()
        self.transactions = [dict(t) for t in tx_rows]

        # Load Findings
        findings_rows = conn.execute("SELECT * FROM audit_findings WHERE engagement_id = ? ORDER BY id ASC", (self.engagement_id,)).fetchall()
        self.findings = [dict(f) for f in findings_rows]

        # Load Ledgers & Distinct Tracked Accounts
        ledger_rows = conn.execute("SELECT * FROM ledgers WHERE engagement_id = ?", (self.engagement_id,)).fetchall()
        self.ledgers = [dict(l) for l in ledger_rows]
        
        distinct_ledger_names = set(t["ledger"] for t in self.transactions if t.get("ledger"))
        self.distinct_ledgers_count = len(distinct_ledger_names) if distinct_ledger_names else len(self.ledgers)

        conn.close()

    def process_query(
        self,
        query: str,
        finding_id: Optional[int] = None,
        transaction_id: Optional[int] = None,
        voucher_no: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main execution entry point: detects intent, executes deterministic pre-calculations,
        and constructs evidence-based response with inspectable source records.
        """
        intent = detect_intent(query)
        res = None

        if finding_id or intent == "CREATE_AUDIT_OBSERVATION":
            res = self._handle_audit_observation(query, finding_id)
        elif intent == "EXPLAIN_FLAGGED_TRANSACTION":
            res = self._handle_explain_flagged_transaction(query, transaction_id, voucher_no)
        elif intent == "UNUSUAL_TRANSACTIONS":
            res = self._handle_unusual_transactions(query)
        elif intent == "YOY_CHANGES":
            res = self._handle_yoy_changes(query)
        elif intent == "UNMATCHED_BANK":
            res = self._handle_unmatched_bank(query)
        elif intent == "SUMMARIZE_EXCEPTIONS":
            res = self._handle_summarize_exceptions(query)
        elif intent == "ACCOUNTS_REQUIRE_REVIEW":
            res = self._handle_accounts_require_review(query)
        elif intent == "EXPLAIN_RECONCILIATION":
            res = self._handle_explain_reconciliation(query)
        elif intent == "FINANCIAL_MOVEMENT":
            res = self._handle_financial_movement(query)
        elif intent == "CASH_STATUTORY_LIMITS":
            res = self._handle_cash_limits(query)
        elif intent == "LARGEST_TRANSACTIONS":
            res = self._handle_largest_transactions(query)
        else:
            res = self._handle_general_query(query)

        # Provenance attribution & Local LLM synthesis for audit explanations
        from backend.app.services.local_ai_provider import LocalAIModelManager, sanitize_audit_text
        from backend.app.ai.context_builder import AIContextBoundary
        config = LocalAIModelManager.get_config()
        provider = LocalAIModelManager.get_active_provider()
        
        provenance = "DETERMINISTIC_RULE"
        model_name = config.get("model_name", "builtin-deterministic")

        # Refusal & Safety Guard:
        # Never pass unresolvable-ID responses, missing-record notices, or safety refusals to the LLM
        # to ensure hallucinated compliance never overwrites a verified audit refusal.
        deterministic_response = res.get("response", "")
        is_refusal_or_unresolved = (
            "could not be resolved" in deterministic_response.lower() or
            "not found" in deterministic_response.lower() or
            "no matching" in deterministic_response.lower() or
            "please verify" in deterministic_response.lower()
        )

        if not is_refusal_or_unresolved and config.get("is_enabled", True) and config.get("engine") == "LMStudio":
            try:
                is_avail, _, _ = provider.check_health()
                if is_avail:
                    # Grounded prompt incorporating deterministic metrics & complete relevant evidence
                    calc_metrics = res.get("calculated_metrics", {})
                    evidence_list = res.get("evidence", [])
                    source_txs = res.get("source_transactions", [])
                    
                    # Build scoped, redacted context through dedicated AIContextBoundary
                    boundary_data = {
                        "transactions": source_txs if source_txs else self.transactions[:25],
                    }
                    if res.get("intent") == "CREATE_AUDIT_OBSERVATION" and evidence_list:
                        boundary_data["finding"] = evidence_list[0]
                    elif res.get("intent") == "EXPLAIN_RECONCILIATION" and calc_metrics:
                        boundary_data["reconciliation_summary"] = calc_metrics

                    scoped_context, boundary_meta = AIContextBoundary.build_engagement_context(
                        engagement_id=self.engagement_id,
                        client_name=self.client_info.get("name", "Client"),
                        financial_year=self.engagement.get("financial_year", "2024-25"),
                        task_type=res.get("intent", "AUDIT_QUERY"),
                        relevant_data=boundary_data,
                        max_records=25
                    )

                    sanitized_query, _ = sanitize_audit_text(query, client_name=self.client_info.get("name", "Client"))
                    metrics_str = json.dumps(calc_metrics, default=str) if calc_metrics else "None"
                    evidence_str = json.dumps(evidence_list[:10], default=str) if evidence_list else "None"

                    if res.get("intent") == "CREATE_AUDIT_OBSERVATION":
                        instructions = (
                            "INSTRUCTIONS FOR LOCAL AI AUDITOR ASSISTANT:\n"
                            "1. Synthesize an expert Chartered Accountant advisory review of this specific statutory audit observation.\n"
                            "2. Formulate 3-4 precise, technical management inquiry questions to address to the client's finance head / CFO.\n"
                            "3. Detail specific substantive working paper testing procedures required under the cited ICAI SAs to verify and close this finding.\n"
                            "4. Strictly maintain the authoritative numbers, standards, and statutes without contradiction."
                        )
                    else:
                        instructions = (
                            "INSTRUCTIONS FOR LOCAL AI AUDITOR ASSISTANT:\n"
                            "1. Explain the underlying audit issue clearly based strictly on the authoritative facts above.\n"
                            "2. DO NOT contradict the deterministic calculations or claim compliance when violations exist.\n"
                            "3. Provide actionable statutory audit guidance referencing relevant Indian accounting/tax standards."
                        )

                    prompt = (
                        f"{scoped_context}\n\n"
                        f"AUTHORITATIVE DETERMINISTIC AUDIT FINDINGS (CANNOT BE OVERRULED):\n"
                        f"- Rule-Calculated Metrics: {metrics_str}\n"
                        f"- Corroborating Evidence: {evidence_str}\n"
                        f"- Deterministic Analysis:\n{deterministic_response}\n\n"
                        f"AUDITOR INQUIRY: {sanitized_query}\n\n"
                        f"{instructions}"
                    )

                    gen_res = provider.generate(
                        prompt=prompt,
                        system_prompt="You are a professional statutory auditor assistant. Ground your response strictly in the authoritative evidence provided.",
                        max_tokens=1024
                    )
                    gen_text = gen_res.get("text", "").strip() if gen_res else ""
                    if gen_text and len(gen_text) > 20:
                        # Hallucination guard: If authoritative deterministic results found violations/anomalies,
                        # reject model output that contradicts them with false compliance claims.
                        viol_count = calc_metrics.get("violations_count", 0) or calc_metrics.get("critical_count", 0) or len(res.get("evidence", []))
                        is_contradiction = (
                            viol_count > 0 and 
                            any(phrase in gen_text.lower() for phrase in ["no issues found", "everything is compliant", "all transactions are compliant", "zero findings"])
                        )

                        if is_contradiction:
                            logging.getLogger(__name__).warning("Model output contradicted authoritative deterministic findings; suppressing model response.")
                            provenance = "FALLBACK"
                        else:
                            # Preserve authoritative deterministic analysis and provide model explanation
                            res["response"] = (
                                f"{deterministic_response}\n\n"
                                f"---\n"
                                f"### 🤖 Local AI Narrative Synthesis ({gen_res.get('model', model_name)})\n"
                                f"> *Advisory note: Synthesized by local LLM. Numerical metrics, findings, and evidence above are authoritative.*  \n\n"
                                f"{gen_text}"
                            )
                            res["ai_narrative"] = gen_text
                            provenance = "LOCAL_LLM"
                            model_name = gen_res.get("model", model_name)
            except Exception as e:
                logging.getLogger(__name__).warning("Local LLM synthesis fallback triggered: %s", e)
                # Retain deterministic response as fallback
                provenance = "DETERMINISTIC_RULE"

        res["provenance"] = provenance
        res["model_name"] = model_name
        return res

    # ----------------------------------------------------------------------
    # INTENT HANDLER 1: Unusual Transactions
    # ----------------------------------------------------------------------
    def _handle_unusual_transactions(self, query: str) -> Dict[str, Any]:
        # Deterministic Anomaly Calculation
        anomaly_results = detect_all_anomalies(self.engagement_id)
        anomalies = anomaly_results.get("anomalies", [])

        # Distinct anomalous transactions calculation
        distinct_tx_ids = set()
        for a in anomalies:
            t_id = a.get("transaction_id") or a.get("transaction", {}).get("id")
            if t_id:
                distinct_tx_ids.add(t_id)

        distinct_count = len(distinct_tx_ids)
        total_flags = len(anomalies)

        critical_count = sum(1 for a in anomalies if a.get("severity") == "CRITICAL")
        high_count = sum(1 for a in anomalies if a.get("severity") == "HIGH")
        medium_count = sum(1 for a in anomalies if a.get("severity") == "MEDIUM")

        top_anomalies = sorted(anomalies, key=lambda a: float(a.get("anomaly_score") or 0.0), reverse=True)[:8]

        narrative = f"""### 🚨 Unusual Transaction & Anomaly Analysis
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})
**Client:** {self.client_info.get('name', 'Client')}

The Hybrid AI Anomaly Engine analyzed **{len(self.transactions):,}** transactions and identified **{distinct_count}** unusual transaction(s) across **{total_flags}** detection flags:
- 🔴 **Critical Severity:** {critical_count} flag(s) requiring mandatory substantive audit check
- 🟠 **High Severity:** {high_count} flag(s) with statistically significant or statutory deviation
- 🟡 **Medium Severity:** {medium_count} flag(s)

#### Key Patterns Identified:
"""
        patterns_count: Dict[str, int] = {}
        for a in anomalies:
            pat = a.get("pattern_type") or a.get("detected_pattern") or a.get("level") or "General Deviation"
            patterns_count[pat] = patterns_count.get(pat, 0) + 1

        for pat, count in sorted(patterns_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            narrative += f"- **{pat}:** {count} occurrence(s)\n"

        narrative += f"\n*Click on any transaction in the **Supporting Evidence** table below to inspect complete ledger, party, and voucher details.*"

        evidence = []
        source_txs = []
        for a in top_anomalies:
            tx_obj = a.get("transaction") or {}
            tx_id = a.get("transaction_id") or tx_obj.get("id")
            tx = next((t for t in self.transactions if t.get("id") == tx_id), None) or tx_obj

            amt = float(tx_obj.get("amount") or (tx.get("amount") if tx else 0.0) or a.get("evidence", {}).get("amount", 0.0) or 0.0)
            if amt == 0.0 and tx:
                amt = float(tx.get("debit") or tx.get("credit") or 0.0)

            date_val = tx_obj.get("date") or (tx.get("date") if tx else None) or a.get("evidence", {}).get("date") or "—"
            vch_val = tx_obj.get("voucher_no") or (tx.get("voucher_no") if tx else None) or a.get("evidence", {}).get("voucher") or (f"TX-{tx_id}" if tx_id else "—")
            inv_val = tx_obj.get("invoice_no") or (tx.get("invoice_no") if tx else None) or "—"
            ledg_val = tx_obj.get("ledger") or (tx.get("ledger") if tx else None) or a.get("evidence", {}).get("ledger") or "General Ledger"
            party_val = tx_obj.get("party_name") or (tx.get("party_name") if tx else None) or a.get("evidence", {}).get("party") or "Direct / Cash"
            pat_val = a.get("pattern_type") or a.get("detected_pattern") or a.get("level") or "Statistical Outlier"

            item = {
                "id": tx_id,
                "date": date_val,
                "voucher_no": vch_val,
                "invoice_no": inv_val,
                "ledger": ledg_val,
                "party_name": party_val,
                "amount": amt,
                "amount_formatted": f"₹{amt:,.2f}",
                "anomaly_score": round(float(a.get("anomaly_score") or 0.0), 1),
                "severity": a.get("severity", "HIGH"),
                "rule_or_pattern": pat_val,
                "reason": a.get("explanation") or a.get("recommended_review") or "Statistical outlier detected",
                "recommended_action": a.get("recommended_review") or "Perform substantive voucher verification"
            }
            evidence.append(item)
            if tx and tx not in source_txs:
                source_txs.append(tx)

        return {
            "query": query,
            "intent": "UNUSUAL_TRANSACTIONS",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_transactions": len(self.transactions),
                "distinct_anomalous_transactions": distinct_count,
                "total_anomaly_flags": total_flags,
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count
            },
            "evidence": evidence,
            "source_transactions": source_txs,
            "suggested_actions": [
                "Perform 100% voucher inspection for Critical severity items",
                "Obtain external third-party balance confirmations for flagged counterparties",
                "Verify tax disallowance applicability under Section 40A(3)"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 2: Explain Flagged Transaction
    # ----------------------------------------------------------------------
    def _handle_explain_flagged_transaction(
        self,
        query: str,
        transaction_id: Optional[int] = None,
        voucher_no: Optional[str] = None
    ) -> Dict[str, Any]:
        target_tx = None
        
        # 1. Look up by transaction ID if provided
        if transaction_id:
            target_tx = next((t for t in self.transactions if t.get("id") == transaction_id), None)

        # 2. Extract voucher number from query if present
        if not target_tx and not voucher_no:
            match = re.search(r'\b(V-[A-Za-z0-9_-]+|INV-[A-Za-z0-9_-]+|\b\d{1,6}\b)', query, re.IGNORECASE)
            if match:
                candidate = match.group(1).upper()
                target_tx = next((t for t in self.transactions if (t.get("voucher_no") or "").upper() == candidate or (t.get("invoice_no") or "").upper() == candidate or str(t.get("id")) == candidate), None)

        # 3. Look up by explicit voucher_no parameter
        if not target_tx and voucher_no:
            target_tx = next((t for t in self.transactions if (t.get("voucher_no") or "").upper() == voucher_no.upper()), None)

        # 4. Fallback to highest risk flagged transaction in findings/anomalies only if no specific identifier was requested
        if not target_tx:
            if transaction_id or voucher_no:
                # User asked for a specific transaction/voucher that does not exist in this engagement
                identifier = f"ID #{transaction_id}" if transaction_id else f"Voucher '{voucher_no}'"
                return {
                    "query": query,
                    "intent": "EXPLAIN_FLAGGED_TRANSACTION",
                    "response": f"Transaction {identifier} could not be resolved from the records of this audit engagement. Please verify the transaction ID or voucher reference.",
                    "disclaimer": MANDATORY_DISCLAIMER,
                    "evidence": [],
                    "source_transactions": []
                }
            anomaly_results = detect_all_anomalies(self.engagement_id)
            anoms = anomaly_results.get("anomalies", [])
            if anoms:
                top_anom = anoms[0]
                target_tx = next((t for t in self.transactions if t.get("id") == top_anom.get("transaction_id")), None)

        if not target_tx:
            if self.transactions and not (transaction_id or voucher_no):
                target_tx = self.transactions[0]
            else:
                return {
                    "query": query,
                    "intent": "EXPLAIN_FLAGGED_TRANSACTION",
                    "response": "No matching or flagged transactions are available in the currently selected audit engagement to explain.",
                    "disclaimer": MANDATORY_DISCLAIMER,
                    "evidence": [],
                    "source_transactions": []
                }

        # Calculate exact violations for target_tx
        t_id = target_tx.get("id")
        v_no = target_tx.get("voucher_no") or f"TX-{t_id}"
        amt = float(target_tx.get("amount") or target_tx.get("debit") or target_tx.get("credit") or 0.0)
        ledger = target_tx.get("ledger") or "General"
        party = target_tx.get("party_name") or "Direct"
        date_str = target_tx.get("date") or "—"
        desc = target_tx.get("description") or "—"

        # Check in findings
        related_findings = [f for f in self.findings if str(v_no).lower() in str(f.get("description", "")).lower() or str(v_no).lower() in str(f.get("actual_value", "")).lower() or str(t_id) in str(f.get("actual_value", ""))]
        
        # Check in anomaly engine
        anomaly_results = detect_all_anomalies(self.engagement_id)
        rel_anom = next((a for a in anomaly_results.get("anomalies", []) if a.get("transaction_id") == t_id or a.get("voucher_no") == v_no), None)

        reasons = []
        if rel_anom:
            reasons.append(f"**{rel_anom.get('detected_pattern')}:** {rel_anom.get('explanation')}")
        for f in related_findings:
            reasons.append(f"**{f.get('title')}:** {f.get('reason') or f.get('description')}")

        if not reasons:
            # Evidence-based classification check
            is_cash_ledger = any(k in ledger.lower() for k in ['cash', 'petty cash', 'cash in hand'])
            is_cash = is_cash_ledger or any(k in desc.lower() or k in str(target_tx.get('transaction_type', '')).lower() for k in ['cash', 'petty cash'])
            debit_val = float(target_tx.get('debit') or 0.0)
            credit_val = float(target_tx.get('credit') or 0.0)
            tx_type_str = str(target_tx.get('transaction_type') or '').lower()

            is_payment = (
                (is_cash_ledger and credit_val > 0) or
                (not is_cash_ledger and debit_val > 0 and 'receipt' not in tx_type_str) or
                ('payment' in tx_type_str or 'paid' in desc.lower() or 'expense' in desc.lower())
            )
            is_receipt = (
                (is_cash_ledger and debit_val > 0) or
                (not is_cash_ledger and credit_val > 0 and 'payment' not in tx_type_str) or
                ('receipt' in tx_type_str or 'received' in desc.lower())
            )

            if is_cash and is_receipt and amt >= 200000.0:
                reasons.append(f"**Section 269ST Limit:** High-value cash receipt of ₹{amt:,.2f} equals or exceeds statutory threshold of ₹2,00,000 (Clause 31 Form 3CD).")
            elif is_cash and is_payment and amt > 10000.0:
                reasons.append(f"**Section 40A(3) Limit:** Cash expenditure of ₹{amt:,.2f} exceeds statutory payment threshold of ₹10,000 to a person in a day (Clause 21(d) Form 3CD).")
            elif not desc or len(desc.strip()) < 3:
                reasons.append("**Missing Narration:** Voucher lacks documented business narration / substance.")
            else:
                reasons.append("No active statutory findings or statistical anomaly flags recorded for this transaction in the current audit engagement.")

        narrative = f"""### 🔍 Factual Explanation for Voucher {v_no}
- **Transaction ID:** #{t_id}
- **Date:** {date_str}
- **Ledger Account:** `{ledger}`
- **Counterparty:** {party}
- **Amount:** ₹{amt:,.2f} ({'Debit' if float(target_tx.get('debit') or 0.0) > 0 else 'Credit'})
- **Narration:** {desc}

#### 📋 Audit Findings & Flagging Reasons:
"""
        for r in reasons:
            narrative += f"- {r}\n"

        narrative += f"""
#### 🛠️ Recommended Substantive Procedure:
1. Examine physical tax invoice, GRN, and authorized payment approval voucher.
2. Confirm banking mode of payment (Account Payee Cheque / NEFT / RTGS) for Section 40A(3) compliance.
3. Review GST Input Tax Credit claim in GSTR-3B against 2B matching records.
"""

        evidence_item = {
            "id": t_id,
            "date": date_str,
            "voucher_no": v_no,
            "invoice_no": target_tx.get("invoice_no") or "—",
            "ledger": ledger,
            "party_name": party,
            "amount": amt,
            "amount_formatted": f"₹{amt:,.2f}",
            "reasons": reasons,
            "severity": rel_anom.get("severity") if rel_anom else "HIGH"
        }

        return {
            "query": query,
            "intent": "EXPLAIN_FLAGGED_TRANSACTION",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "transaction_id": t_id,
                "voucher_no": v_no,
                "amount": amt,
                "violations_count": len(reasons)
            },
            "evidence": [evidence_item],
            "source_transactions": [target_tx],
            "suggested_actions": [
                "Mark as verified in General Ledger review",
                "Attach working paper documentation note",
                "Issue management query for missing invoice proof"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 3: Year-on-Year Changes
    # ----------------------------------------------------------------------
    def _handle_yoy_changes(self, query: str) -> Dict[str, Any]:
        # Deterministic YoY Calculation
        yoy_data = run_yoy_comparison(self.engagement_id, threshold_pct=10.0)
        
        exec_items = yoy_data.get("executive_comparison", [])
        major_ledgers = yoy_data.get("major_ledgers_comparison", [])
        top_ledgers = major_ledgers[:6]
        summary = yoy_data.get("summary", {})

        cy_fy = yoy_data.get("current_financial_year", "CY")
        py_fy = yoy_data.get("previous_financial_year", "PY")

        narrative = f"""### 📈 Year-on-Year (YoY) Financial Movement Analysis
**Comparison Period:** {py_fy} (Previous Year) vs {cy_fy} (Current Year)
**Configured Tolerance:** 10.0% | **Materiality Cutoff:** ₹50,000

#### 🏆 Major Ledgers with Largest Absolute Variances:
"""
        evidence = []
        for l in top_ledgers:
            acc = l.get("account_name")
            py_val = l.get("previous_year")
            cy_val = l.get("current_year")
            abs_diff = l.get("absolute_difference")
            pct_diff = l.get("percentage_difference")
            dir_m = l.get("movement_direction")
            is_sig = l.get("is_significant")

            sig_badge = "🚨 **SIGNIFICANT**" if is_sig else "Normal"
            pct_s = f"{pct_diff:+.1f}%" if pct_diff is not None else "New Balance"
            narrative += f"- **{acc}:** {py_fy}: ₹{py_val:,.2f} → {cy_fy}: ₹{cy_val:,.2f} | **Variance:** {abs_diff:+,.2f} ({pct_s}) [{dir_m}] — {sig_badge}\n"
            
            evidence.append({
                "item_key": l.get("item_key"),
                "account_name": acc,
                "group": l.get("group"),
                "previous_year": py_val,
                "current_year": cy_val,
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "movement_direction": dir_m,
                "risk": l.get("risk"),
                "is_significant": is_sig
            })

        narrative += f"""
#### 💼 Key Financial Statement Shifts:
- **Revenue from Operations:** {summary.get('revenue_growth_pct', 0.0):+.1f}% shift
- **Total Expenditure:** {summary.get('expense_growth_pct', 0.0):+.1f}% shift
- **Gross Margin:** {summary.get('gross_margin_cy', 0.0):.1f}% in {cy_fy} vs {summary.get('gross_margin_py', 0.0):.1f}% in {py_fy}
- **Significant Movement Count:** {summary.get('significant_movements_count', 0)} line item(s) breached threshold
"""

        # Fetch relevant transactions for top ledgers
        top_ledger_names = [l.get("account_name", "").lower() for l in top_ledgers]
        relevant_txs = [t for t in self.transactions if (t.get("ledger") or "").lower() in top_ledger_names][:15]

        return {
            "query": query,
            "intent": "YOY_CHANGES",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": summary,
            "evidence": evidence,
            "source_transactions": relevant_txs,
            "suggested_actions": [
                "Perform analytical review inquiry for variances exceeding 20%",
                "Verify cut-off procedures for Revenue and Purchases at year-end",
                "Corroborate debtor increase with credit terms and subsequent realizations"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 4: Unmatched Bank Transactions
    # ----------------------------------------------------------------------
    def _handle_unmatched_bank(self, query: str) -> Dict[str, Any]:
        conn = get_db_connection()
        bank_items = []
        try:
            bank_items_rows = conn.execute("""
                SELECT ri.*, r.title as recon_title
                FROM reconciliation_items ri
                JOIN reconciliations r ON ri.recon_id = r.id
                WHERE r.engagement_id = ? AND r.recon_type LIKE '%Bank%'
            """, (self.engagement_id,)).fetchall()
            bank_items = [dict(r) for r in bank_items_rows]
        except Exception:
            bank_items = []
        finally:
            conn.close()

        unmatched_bank = [
            i for i in bank_items 
            if i.get("match_status") in ["UNMATCHED", "UNMATCHED_BANK", "Missing in Books"] 
            or i.get("match_level") in ["UNMATCHED_BANK", "UNMATCHED"]
            or (i.get("status") in ["Unmatched", "Mismatch"] and not (i.get("book_tx_id") or i.get("amount_a")))
        ]
        unmatched_books = [
            i for i in bank_items 
            if i.get("match_status") in ["UNMATCHED_BOOKS", "Missing in Bank"] 
            or i.get("match_level") in ["UNMATCHED_BOOKS", "UNMATCHED_BOOK"]
            or (i.get("status") in ["Unmatched", "Mismatch"] and not (i.get("bank_tx_id") or i.get("amount_b")))
        ]
        amount_diffs = [
            i for i in bank_items 
            if abs(float(i.get("amount_difference") or i.get("difference") or 0.0)) > 0.01
        ]

        # If no explicit bank reconciliation items recorded yet, evaluate bank ledger entries directly
        if not bank_items:
            bank_txs = [t for t in self.transactions if any(k in (t.get("ledger") or "").lower() for k in ["bank", "hdfc", "sbi", "icici", "axis"])]
            unpresented = [t for t in bank_txs if not t.get("payment_date") or t.get("payment_date") != t.get("date")]
            
            narrative = f"""### 🏦 Bank Reconciliation Analysis
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})

The audit engine evaluated **{len(bank_txs)}** bank transactions from the general ledger:
- **Total Bank Transactions in Books:** {len(bank_txs)} entries
- **Potential Unpresented Cheques / Timing Differences:** {len(unpresented)} entries
- **Direct Bank Ledgers Identified:** {', '.join(set([t.get('ledger') for t in bank_txs])) or 'Bank Account'}

*Tip: Upload the official Bank Statement (.csv / .xlsx / .pdf) in the **Reconciliation** module to execute 7-attribute automated matching.*
"""
            evidence = []
            for t in unpresented[:8]:
                amt = float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)
                evidence.append({
                    "id": t.get("id"),
                    "date": t.get("date"),
                    "voucher_no": t.get("voucher_no"),
                    "ledger": t.get("ledger"),
                    "party_name": t.get("party_name") or "Direct",
                    "amount": amt,
                    "amount_formatted": f"₹{amt:,.2f}",
                    "match_status": "Timing Difference / Unpresented",
                    "reason": "Voucher booking date differs from clearance / payment date"
                })

            return {
                "query": query,
                "intent": "UNMATCHED_BANK",
                "response": narrative.strip(),
                "disclaimer": MANDATORY_DISCLAIMER,
                "calculated_metrics": {
                    "total_bank_txs": len(bank_txs),
                    "potential_timing_diffs": len(unpresented)
                },
                "evidence": evidence,
                "source_transactions": unpresented[:10],
                "suggested_actions": [
                    "Inspect Bank Confirmation Certificate as of March 31st",
                    "Verify subsequent realization of unpresented cheques in April",
                    "Reconcile direct bank charges and interest credits"
                ]
            }

        # Format narrative with recorded bank reconciliation data
        narrative = f"""### 🏦 Bank Reconciliation Exceptions & Unmatched Items
**Reconciliation Set:** {bank_items[0].get('recon_title', 'Bank Reconciliation')}

- **Total Reconciliation Items:** {len(bank_items)}
- **Unmatched Bank Entries (Missing in Books):** {len(unmatched_bank)}
- **Unmatched Book Entries (Missing in Bank):** {len(unmatched_books)}
- **Amount / Date Discrepancies:** {len(amount_diffs)}

#### Key Unmatched Transactions:
"""
        evidence = []
        for item in (unmatched_bank + unmatched_books + amount_diffs)[:8]:
            bank_amt = float(item.get("bank_amount") or item.get("amount_b") or 0.0)
            book_amt = float(item.get("book_amount") or item.get("amount_a") or 0.0)
            diff = float(item.get("amount_difference") or item.get("difference") or (bank_amt - book_amt))
            stat = item.get("match_status") or item.get("match_level") or item.get("status") or "Unmatched"
            desc = item.get("bank_description") or item.get("description_b") or item.get("book_description") or item.get("description_a") or "N/A"
            narrative += f"- **[{stat}]:** Bank: ₹{bank_amt:,.2f} | Books: ₹{book_amt:,.2f} | Diff: ₹{diff:+,.2f} ({desc})\n"
            evidence.append(item)

        return {
            "query": query,
            "intent": "UNMATCHED_BANK",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_items": len(bank_items),
                "unmatched_bank_count": len(unmatched_bank),
                "unmatched_books_count": len(unmatched_books),
                "amount_diffs_count": len(amount_diffs)
            },
            "evidence": evidence,
            "source_transactions": [],
            "suggested_actions": [
                "Trace uncredited lodgements to bank deposit slips",
                "Verify bank interest and auto-debit charges booked by bank",
                "Obtain CA bank confirmation under SA 505"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 5: Summarize Major Audit Exceptions
    # ----------------------------------------------------------------------
    def _handle_summarize_exceptions(self, query: str) -> Dict[str, Any]:
        critical = [f for f in self.findings if f.get("severity") == "CRITICAL"]
        high = [f for f in self.findings if f.get("severity") == "HIGH"]
        medium = [f for f in self.findings if f.get("severity") == "MEDIUM"]
        low = [f for f in self.findings if f.get("severity") == "LOW"]

        total_turnover = sum(float(t.get("debit") or 0.0) for t in self.transactions)

        narrative = f"""### 📑 Executive Summary of Audit Findings & Exceptions
**Engagement:** {self.engagement.get('title')} | **Financial Year:** {self.engagement.get('financial_year')}
**Client PAN:** {self.client_info.get('pan', 'N/A')} | **GSTIN:** {self.client_info.get('gstin', 'N/A')}

#### 🎯 Audit Risk Rating: **{'HIGH RISK' if critical or len(high) > 2 else ('MEDIUM RISK' if high else 'LOW RISK')}**
The automated audit engine evaluated **{len(self.transactions):,}** transactions (Turnover: **₹{total_turnover:,.2f}**) and logged **{len(self.findings)}** exception(s):

| Severity Tier | Count | Key Exception Category |
|---|---|---|
| 🔴 **CRITICAL** | **{len(critical)}** | Statutory cash violations (Sec 40A(3)/269ST), Trial Balance mismatch |
| 🟠 **HIGH** | **{len(high)}** | GSTIN invalid structures, Duplicate vouchers, High-risk statistical outliers |
| 🟡 **MEDIUM** | **{len(medium)}** | Missing narrations, Round sum transactions, Weekend postings |
| 🟢 **LOW** | **{len(low)}** | General classification & minor documentation notes |

#### ⚠️ High Priority Matters Requiring Immediate CA Review:
"""
        evidence = []
        for f in (critical + high)[:6]:
            code = f.get("finding_code") or f"FIND-{f.get('id')}"
            narrative += f"- **[{f.get('severity')}] {code}:** {f.get('title')} — *{f.get('reason') or f.get('description')}*\n"
            evidence.append(f)

        if not critical and not high:
            narrative += "- No Critical or High severity exceptions flagged in the current dataset.\n"

        narrative += f"""
#### 📌 Recommended Audit Actions:
1. Issue formal Management Representation Letter queries for all {len(critical) + len(high)} Critical/High exceptions.
2. Complete working paper cross-referencing in Form 3CD Clauses 21(d) & 31.
3. Validate Input Tax Credit reconciliation with GSTR-2B before closing statutory sign-off.
"""

        return {
            "query": query,
            "intent": "SUMMARIZE_EXCEPTIONS",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_findings": len(self.findings),
                "critical_count": len(critical),
                "high_count": len(high),
                "medium_count": len(medium),
                "low_count": len(low)
            },
            "evidence": evidence,
            "source_transactions": self.transactions[:10],
            "suggested_actions": [
                "Export working paper exceptions memorandum",
                "Mark reviewed findings as Resolved or Waived with auditor justification",
                "Generate Final Audit Report PDF"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 6: Accounts Requiring Review
    # ----------------------------------------------------------------------
    def _handle_accounts_require_review(self, query: str) -> Dict[str, Any]:
        # Identify high risk ledgers
        ledger_risk_map: Dict[str, Dict[str, Any]] = {}
        
        # 1. Ledgers with findings
        for f in self.findings:
            l = f.get("ledger_name") or f.get("ledger")
            if l:
                if l not in ledger_risk_map:
                    ledger_risk_map[l] = {"findings": 0, "critical": 0, "reasons": []}
                ledger_risk_map[l]["findings"] += 1
                if f.get("severity") in ["CRITICAL", "HIGH"]:
                    ledger_risk_map[l]["critical"] += 1
                ledger_risk_map[l]["reasons"].append(f.get("title"))

        # 2. Check for suspense or abnormal balances
        for l in self.ledgers:
            name = l.get("ledger_name", "")
            cl = float(l.get("closing_balance") or 0.0)
            if "suspense" in name.lower() or "clearing" in name.lower():
                if name not in ledger_risk_map:
                    ledger_risk_map[name] = {"findings": 1, "critical": 1, "reasons": []}
                ledger_risk_map[name]["reasons"].append(f"Suspense / Unadjusted head with non-zero balance of ₹{cl:,.2f}")
            elif "cash" in name.lower() and cl < 0:
                if name not in ledger_risk_map:
                    ledger_risk_map[name] = {"findings": 1, "critical": 1, "reasons": []}
                ledger_risk_map[name]["reasons"].append(f"Abnormal negative cash balance: ₹{cl:,.2f}")

        # 3. Check YoY significant movements
        yoy = run_yoy_comparison(self.engagement_id, threshold_pct=15.0)
        for ml in yoy.get("major_ledgers_comparison", []):
            if ml.get("is_significant"):
                name = ml.get("account_name")
                if name not in ledger_risk_map:
                    ledger_risk_map[name] = {"findings": 0, "critical": 0, "reasons": []}
                ml_pct = ml.get('percentage_difference')
                ml_pct_s = f"{ml_pct:+.1f}%" if ml_pct is not None else "New Balance"
                ledger_risk_map[name]["reasons"].append(f"Significant YoY variance of ₹{ml.get('absolute_difference'):+,.2f} ({ml_pct_s})")

        narrative = f"""### 📋 Accounts & Ledgers Requiring In-Depth Review
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})

The audit engine identified **{len(ledger_risk_map)}** ledger account(s) that require specific substantive examination:

"""
        evidence = []
        for l_name, data in sorted(ledger_risk_map.items(), key=lambda x: (x[1]["critical"], x[1]["findings"]), reverse=True)[:6]:
            uniq_reasons = list(dict.fromkeys(data["reasons"]))[:2]
            r_str = "; ".join(uniq_reasons)
            narrative += f"- **`{l_name}`** ({'🔴 High Risk' if data['critical'] > 0 else '🟡 Moderate Risk'}):\n  • *Triggers:* {r_str}\n"
            
            # Find sample transactions for this ledger
            l_txs = [t for t in self.transactions if (t.get("ledger") or "").lower() == l_name.lower()]
            tot_amt = sum(float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0) for t in l_txs)
            evidence.append({
                "account_name": l_name,
                "transaction_count": len(l_txs),
                "total_turnover": tot_amt,
                "total_turnover_formatted": f"₹{tot_amt:,.2f}",
                "exception_count": data["findings"],
                "critical_exceptions": data["critical"],
                "reasons": uniq_reasons
            })

        narrative += f"""
#### 🔬 Audit Strategy:
- Focus substantive voucher testing on the top flagged accounts.
- Verify suspense clearing entries before final Trial Balance lock.
"""

        # Fetch relevant transactions for flagged ledgers
        flagged_names = [l.lower() for l in ledger_risk_map.keys()]
        rel_txs = [t for t in self.transactions if (t.get("ledger") or "").lower() in flagged_names][:15]

        return {
            "query": query,
            "intent": "ACCOUNTS_REQUIRE_REVIEW",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_accounts_requiring_review": len(ledger_risk_map),
                "high_risk_accounts_count": sum(1 for d in ledger_risk_map.values() if d["critical"] > 0)
            },
            "evidence": evidence,
            "source_transactions": rel_txs,
            "suggested_actions": [
                "Drill down into General Ledger module for each flagged account",
                "Verify suspense accounts are brought to zero before signing report",
                "Perform negative balance confirmation procedures"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 7: Explain Reconciliation Differences
    # ----------------------------------------------------------------------
    def _handle_explain_reconciliation(self, query: str) -> Dict[str, Any]:
        conn = get_db_connection()
        all_recon_exceptions = []
        try:
            recon_rows = conn.execute("""
                SELECT ri.*, r.title as recon_title, r.recon_type
                FROM reconciliation_items ri
                JOIN reconciliations r ON ri.recon_id = r.id
                WHERE r.engagement_id = ?
            """, (self.engagement_id,)).fetchall()
            all_recon_exceptions = [
                dict(r) for r in recon_rows 
                if r.get("match_level") in ["UNMATCHED", "POSSIBLE MATCH"] or r.get("status") in ["Mismatch", "Rejected", "Unmatched"]
            ]
        except Exception:
            all_recon_exceptions = []
        finally:
            conn.close()

        if not all_recon_exceptions:
            narrative = f"""### 🔍 Reconciliation Exception Analysis
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})

- **Status:** No unresolved reconciliation mismatches or GSTIN/amount differences are currently logged in the active reconciliation working papers.
- **Available Toolsets:** You can run automated **GST Reconciliation (GSTR-2B vs Purchase Register)** and **Sales/Purchase Cross-Matching** from the *Reconciliation* navigation menu.
"""
            return {
                "query": query,
                "intent": "EXPLAIN_RECONCILIATION",
                "response": narrative.strip(),
                "disclaimer": MANDATORY_DISCLAIMER,
                "calculated_metrics": {"total_exceptions": 0},
                "evidence": [],
                "source_transactions": []
            }

        narrative = f"""### ⚖️ Reconciliation Exceptions & Tax Variance Breakdown
**Total Flagged Reconciliation Exceptions:** {len(all_recon_exceptions)} item(s)

#### 🔎 Top Reconciliation Discrepancies:
"""
        evidence = []
        for item in all_recon_exceptions[:6]:
            inv = item.get("ref_a") or item.get("ref_b") or "N/A"
            party = item.get("party_a") or item.get("party_b") or "Direct"
            diff = float(item.get("taxable_difference") or item.get("difference") or 0.0)
            tax_diff = float(item.get("tax_difference") or (float(item.get("cgst_difference") or 0.0) + float(item.get("sgst_difference") or 0.0) + float(item.get("igst_difference") or 0.0)))
            stat = item.get("match_level") or item.get("status")

            narrative += f"- **Invoice / Ref {inv} ({party}):** Status: `{stat}` | Taxable Diff: ₹{diff:+,.2f} | Tax Diff: ₹{tax_diff:+,.2f}\n"
            evidence.append(item)

        narrative += f"""
#### 🛡️ Compliance Impact:
- ITC Mismatches in GSTR-2B must be reconciled to prevent demand notices under Section 16(2)(aa) of CGST Act.
- Invoices missing in Purchase Register require verification against physical goods receipts.
"""

        return {
            "query": query,
            "intent": "EXPLAIN_RECONCILIATION",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_exceptions": len(all_recon_exceptions)
            },
            "evidence": evidence,
            "source_transactions": [],
            "suggested_actions": [
                "Issue supplier communication for unuploaded GSTR-1 invoices",
                "Reverse ineligible Input Tax Credit in Table 4(B) of GSTR-3B",
                "Document timing differences in reconciliation working papers"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 8: Create Audit Observation / Memo
    # ----------------------------------------------------------------------
    @staticmethod
    def _map_finding_statutory_framework(target_finding: Dict[str, Any]) -> Dict[str, str]:
        """
        Dynamically maps audit findings to their exact statutory provisions, ICAI Standards on Auditing,
        reporting disclosure obligations (CARO 2020 / Form 3CD / Companies Act), root causes, and substantive procedures.
        """
        code = (target_finding.get("finding_code") or "").upper()
        category = (target_finding.get("category") or "").upper()
        title = (target_finding.get("title") or "").upper()
        rule = target_finding.get("rule_used") or ""
        desc = target_finding.get("description") or target_finding.get("reason") or ""
        rec = target_finding.get("recommended_action") or ""

        # 1. Trial Balance / Double Entry Imbalance
        if "DET-001" in code or "TRIAL BALANCE" in title or ("DEBIT" in title and "CREDIT" in title) or "DOUBLE-ENTRY" in rule.upper():
            return {
                "standard": rule or "Ind AS 1 / AS 1: Presentation of Financial Statements & Double-Entry Equality",
                "statute": "Section 128(1) & Section 129 of Companies Act 2013 (Books of Account & True and Fair View)",
                "icai_sas": "SA 200 (Overall Objectives of Auditor), SA 315 (Material Misstatement Risk), SA 500 (Audit Evidence), SA 705 (Modifications to Audit Opinion)",
                "statutory_disclosure": "Section 143(3)(b) & Section 143(3)(h) of Companies Act 2013 (Proper books maintained / Qualification remarks); CARO 2020 Clause 3(xiv) / Internal Financial Controls over Financial Reporting (IFCoFR)",
                "cause": "Omission of one-sided ledger entries, corrupted data migration from source accounting software, unposted year-end adjusting journal vouchers, or unreconciled suspense accounts.",
                "effect": "Fundamental violation of the double-entry accounting framework preventing generation of balanced Financial Statements under Schedule III; severe audit risk warranting modification or qualification of the statutory audit opinion under SA 705.",
                "recommendation": rec or "Extract full General Ledger journal listing; verify debit/credit aggregates by ledger; review suspense account entries; require management to pass rectifying journal entries prior to signing financial statements."
            }

        # 2. Section 40A(3) Cash Payment
        elif "40A3" in code or "40A(3)" in title or "10,000" in desc or "CASH PAYMENT" in title:
            return {
                "standard": "Section 40A(3) of the Income Tax Act 1961 read with Rule 6DD of Income Tax Rules 1962",
                "statute": "Income Tax Act 1961 - Expenditure Incurred in Cash Exceeding Statutory Limit",
                "icai_sas": "SA 250 (Consideration of Laws and Regulations in an Audit of Financial Statements), SA 500 (Audit Evidence)",
                "statutory_disclosure": "Mandatory reporting under Clause 21(d)(A) & 21(d)(B) of Tax Audit Form 3CD",
                "cause": "Absence of strict petty cash ceilings or failure to enforce mandatory payments via banking channels (account payee cheque/draft/ECS/prescribed electronic modes).",
                "effect": "100% statutory disallowance of violating expenditure under Section 40A(3), resulting in an artificial addition to taxable business income, increased tax demand, and penal interest under Sections 234B and 234C.",
                "recommendation": rec or "Verify payment cash vouchers; examine whether the payment falls under exceptions enumerated in Rule 6DD; report unexempted payments in Form 3CD Clause 21(d) and obtain written management representation."
            }

        # 3. Section 269ST Cash Receipt
        elif "269ST" in code or "269ST" in title or "2,00,000" in desc or "CASH RECEIPT" in title:
            return {
                "standard": "Section 269ST of the Income Tax Act 1961 (Restriction on Cash Transactions of ₹2 Lakhs or More)",
                "statute": "Income Tax Act 1961 - High-Value Cash Receipt Prohibition",
                "icai_sas": "SA 250 (Consideration of Laws and Regulations in an Audit of Financial Statements), SA 240 (Fraud & Regulatory Risk)",
                "statutory_disclosure": "Mandatory reporting under Clause 31(ba), 31(bb), 31(bc) and 31(bd) of Tax Audit Form 3CD",
                "cause": "Acceptance of customer settlements in cash exceeding ₹2,00,000 without treasury controls or billing threshold validations.",
                "effect": "Strict statutory penalty under Section 271DA of the Income Tax Act 1961 equal to 100% of the cash received, levied directly upon the recipient company.",
                "recommendation": rec or "Inspect cash receipt vouchers and bank deposit records; verify whether receipts relate to a single transaction, single day, or single occasion; prepare Form 3CD Clause 31 disclosure and obtain management explanation."
            }

        # 4. Duplicate Transactions
        elif "DUP" in code or "DUPLICATE" in title or "DUPLICATE" in category:
            return {
                "standard": "Ind AS 1 / AS 1: Accrual Basis of Accounting & True and Fair View",
                "statute": "Section 129(1) of Companies Act 2013 (Financial Statements shall give a true and fair view)",
                "icai_sas": "SA 240 (Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements), SA 500 (Audit Evidence), SA 520 (Analytical Procedures)",
                "statutory_disclosure": "Schedule III disclosure adjustments for overstated expenses / trade payables; CARO 2020 Clause 3(xi) if intentional duplicate invoicing is detected",
                "cause": "Breakdown of three-way matching controls (Purchase Order vs Goods Receipt Note vs Vendor Invoice), dual entry by accounts staff, or automated ERP sync retries.",
                "effect": "Overstatement of operational expenses and inflated trade liabilities, leading to understated profitability, unauthorized duplicate cash disbursements, and material misstatement risk.",
                "recommendation": rec or "Cross-reference duplicate vouchers with physical third-party invoices, delivery challans, and e-Way bills; reverse redundant entry and request vendor statement confirmation."
            }

        # 5. GST / GSTIN Non-Compliance
        elif "GST" in code or "GSTIN" in title or "GST" in category:
            return {
                "standard": "Central Goods and Services Tax (CGST) Act 2017 - Section 16(2) (Conditions for Availing Input Tax Credit) & Section 31 (Tax Invoice)",
                "statute": "CGST Act 2017 & State GST Acts - Statutory ITC Eligibility and Matching Framework",
                "icai_sas": "SA 250 (Consideration of Laws and Regulations in an Audit of Financial Statements), SA 500 (Audit Evidence)",
                "statutory_disclosure": "Tax Audit Form 3CD Clause 44 (Break-up of expenditure with GST registered/unregistered entities); GSTR-9C Table 12 (ITC Reconciliation)",
                "cause": "Master vendor data creation without active GSTIN verification; transacting with non-compliant or cancelled GST vendors while claiming input tax credit.",
                "effect": "Disallowance of Input Tax Credit (ITC) under Section 16(2) of CGST Act, demand for tax recovery along with mandatory 18% interest under Section 50, and penal liabilities under Section 122.",
                "recommendation": rec or "Validate vendor GSTIN status on GST common portal; reconcile purchase register against GSTR-2B; reverse ineligible or unreflected ITC in the subsequent GSTR-3B return."
            }

        # 6. Negative Ledger Balance
        elif "BAL" in code or "NEGATIVE" in title or "NEGATIVE" in desc:
            return {
                "standard": "ICAI Technical Guide on Internal Audit & Guidance Note on Tax Audit",
                "statute": "Section 69A of Income Tax Act 1961 (Unexplained Money / Cash Deficits)",
                "icai_sas": "SA 500 (Audit Evidence), SA 240 (Auditor's Responsibilities Relating to Fraud), SA 315",
                "statutory_disclosure": "CARO 2020 Clause 3(xiv) / Internal Financial Controls; Form 3CD observations on cash book discrepancies",
                "cause": "Failure to record cash sales/receipts in chronological sequence; unrecorded collections; timing lag in journalizing banking transfers.",
                "effect": "Physical impossibility of negative cash in hand; high risk of tax department treating negative balances as unexplained cash credits/money under Section 68/69A taxed at peak rate under Section 115BBE (60% + 25% surcharge).",
                "recommendation": rec or "Perform daily chronological cash book reconstruction; identify omitted receipts; conduct immediate surprise physical cash count and obtain management confirmation."
            }

        # 7. Date Inconsistencies / Future Dates / Prior Period
        elif "DATE" in code or "FUTURE" in title or "CUT-OFF" in title:
            return {
                "standard": "AS 5 / Ind AS 8: Net Profit or Loss for the Period, Prior Period Items & Accounting Changes",
                "statute": "Section 128(1) of Companies Act 2013 (Books of Account maintained for every financial year)",
                "icai_sas": "SA 500 (Audit Evidence - Completeness and Cut-off Assertions), SA 700",
                "statutory_disclosure": "Tax Audit Form 3CD Clause 27(b) (Prior period expenses/income); Schedule III disclosure notes",
                "cause": "Lack of period-lock controls in ERP software, post-dated voucher entry errors, or manual override of voucher dates.",
                "effect": "Cut-off assertion violation; distortion of revenue/expense matching across financial periods; misstatement of financial year operating margins.",
                "recommendation": rec or "Perform substantive cut-off testing on vouchers recorded 15 days before and after year-end; reclassify prior period items into appropriate Schedule III disclosure."
            }

        # 8. Round Number Spikes / Suspicious Narrations
        elif "ROUND" in code or "NARR" in code or "ROUND" in title or "NARRATION" in title:
            return {
                "standard": "SA 240: Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements",
                "statute": "Section 37(1) of Income Tax Act 1961 (General Deductions for Business Purposes)",
                "icai_sas": "SA 240 (Journal Entry Testing & Management Override of Controls), SA 315, SA 330 (Responses to Assessed Risks)",
                "statutory_disclosure": "Tax Audit Form 3CD Clause 21(a) (Non-business or personal expenses); CARO 2020 Clause 3(xi)",
                "cause": "Management manual journal entries posted without third-party supporting vouchers or standardized documentation workflows.",
                "effect": "Risk of booking fictitious or non-business expenditures; exposure to disallowance under Section 37(1) and underreporting penalties under Section 270A.",
                "recommendation": rec or "Inspect underlying third-party vendor contracts, approved purchase requisitions, and proof of receipt; confirm genuine commercial purpose of the expenditure."
            }

        # 9. Default Statutory Framework
        else:
            return {
                "standard": rule or "Applicable Accounting Standards (AS / Ind AS) & ICAI Guidance Notes",
                "statute": "Companies Act 2013 & Income Tax Act 1961 Statutory Audit Framework",
                "icai_sas": "SA 200 (Overall Objectives), SA 315 (Assessing Risks), SA 500 (Audit Evidence)",
                "statutory_disclosure": "CARO 2020 / Form 3CD disclosure framework as applicable to the finding category",
                "cause": "Inadequate preventative internal financial controls over transaction authorization and record keeping.",
                "effect": "Risk of statutory non-compliance, financial statement distortion, and potential audit qualification.",
                "recommendation": rec or "Obtain corroborating documentation, verify supporting vouchers, and seek written management representation."
            }

    def _handle_audit_observation(self, query: str, finding_id: Optional[int] = None) -> Dict[str, Any]:
        target_finding = None
        if finding_id:
            target_finding = next((f for f in self.findings if f.get("id") == finding_id), None)
        
        if not target_finding:
            if finding_id:
                return {
                    "query": query,
                    "intent": "CREATE_AUDIT_OBSERVATION",
                    "response": f"Finding ID #{finding_id} could not be resolved from active audit findings for this engagement. Please verify the finding ID.",
                    "disclaimer": MANDATORY_DISCLAIMER,
                    "evidence": [],
                    "source_transactions": []
                }
            # Match finding by exact code or identifier in query
            match = re.search(r'\b(DET-[A-Za-z0-9_-]+|FIND-\d+|F-\d+|\d+)\b', query, re.IGNORECASE)
            if match:
                cand = match.group(1).upper()
                target_finding = next((f for f in self.findings if str(f.get("id")) == cand or (f.get("finding_code") or "").upper() == cand), None)

        # Contextual topic matching
        if not target_finding:
            q_lower = query.lower()
            if "trial balance" in q_lower or "det-001" in q_lower:
                target_finding = next((f for f in self.findings if "DET-001" in (f.get("finding_code") or "").upper() or "TRIAL BALANCE" in (f.get("title") or "").upper()), None)
            elif "40a" in q_lower:
                target_finding = next((f for f in self.findings if "40A3" in (f.get("finding_code") or "").upper() or "40A" in (f.get("title") or "").upper()), None)
            elif "269st" in q_lower:
                target_finding = next((f for f in self.findings if "269ST" in (f.get("finding_code") or "").upper()), None)
            elif "duplicate" in q_lower:
                target_finding = next((f for f in self.findings if "DUP" in (f.get("finding_code") or "").upper()), None)
            elif "gst" in q_lower:
                target_finding = next((f for f in self.findings if "GST" in (f.get("finding_code") or "").upper()), None)

        if not target_finding and self.findings and not finding_id:
            # Pick highest severity finding only if no specific finding was requested
            critical = [f for f in self.findings if f.get("severity") == "CRITICAL"]
            target_finding = critical[0] if critical else self.findings[0]

        if not target_finding:
            return {
                "query": query,
                "intent": "CREATE_AUDIT_OBSERVATION",
                "response": "No active audit findings found in this engagement to generate a working paper observation.",
                "disclaimer": MANDATORY_DISCLAIMER,
                "evidence": [],
                "source_transactions": []
            }

        code = target_finding.get("finding_code") or f"FIND-{target_finding.get('id')}"
        title = target_finding.get("title") or "Audit Exception"
        sev = target_finding.get("severity") or "HIGH"
        rule = target_finding.get("rule_used") or "General Auditing Standard"
        expected = target_finding.get("expected_value") or "Statutory Compliance with accounting standards"
        actual = target_finding.get("actual_value") or "Non-conforming ledger entry"
        desc = target_finding.get("description") or target_finding.get("reason") or "Audit discrepancy noted during substantive testing."
        rec = target_finding.get("recommended_action") or "Obtain supporting invoices and management representation."

        fw = self._map_finding_statutory_framework(target_finding)

        memo = f"""### 📝 STATUTORY AUDIT WORKING PAPER MEMORANDUM
**Working Paper Reference:** `WP-{code.replace('-', '_')}`  
**Client:** {self.client_info.get('name', 'Audit Client')} | **Financial Year:** {self.engagement.get('financial_year', '2024-25')}  
**Finding Reference:** `{code}` | **Severity:** **{sev}** | **Module:** {target_finding.get('module', 'General')}

---

#### 1. Condition (Factual Observation):
{desc}
- **Expected Accounting / Statutory Treatment:** {expected}
- **Actual Condition Identified in Records:** {actual}

#### 2. Criteria (Regulatory & Statutory Framework):
- **Governing Standard / Rule:** {fw['standard']}
- **Applicable Statute:** {fw['statute']}
- **ICAI Standards on Auditing (SAs):** {fw['icai_sas']}
- **Statutory Disclosure Requirement:** {fw['statutory_disclosure']}

#### 3. Cause (Internal Control Breakdown):
{fw['cause']}

#### 4. Effect (Audit Risk & Financial Statement Impact):
{fw['effect']}

#### 5. Recommendation (Substantive Auditor Procedures):
{fw['recommendation']}
- **Auditor Verification Status:** `Requires Management Response & Corroborating Evidence`
- **Lead Auditor Sign-off:** ______________________
"""

        # Resolve associated transactions from affected_records
        aff_ids = []
        try:
            if target_finding.get("affected_records_json"):
                aff_ids = json.loads(target_finding["affected_records_json"])
            elif target_finding.get("affected_records"):
                aff_ids = target_finding["affected_records"]
        except Exception:
            pass
        
        matched_txs = [t for t in self.transactions if t.get("id") in aff_ids] if aff_ids else []
        if not matched_txs:
            matched_txs = [t for t in self.transactions if code in str(t.get("voucher_no", "")) or str(target_finding.get("id")) in str(t.get("id", ""))]

        if matched_txs:
            evidence_list = []
            for tx in matched_txs[:10]:
                tx_copy = dict(tx)
                tx_copy["finding_id"] = target_finding.get("id")
                tx_copy["finding_code"] = code
                tx_copy["severity"] = sev
                evidence_list.append(tx_copy)
        else:
            diff_str = target_finding.get("difference") or ""
            if not diff_str:
                act_str = str(target_finding.get("actual_value") or "")
                num_match = re.search(r'[\d,]+(?:\.\d+)?', act_str)
                if num_match:
                    try:
                        val = float(num_match.group(0).replace(',', ''))
                        diff_str = f"₹{val:,.2f}"
                    except Exception:
                        diff_str = act_str
                else:
                    diff_str = act_str if act_str else "—"
            evidence_item = {
                "id": target_finding.get("id"),
                "finding_id": target_finding.get("id"),
                "finding_code": code,
                "date": f"FY {self.engagement.get('financial_year', '2024-25')}",
                "voucher_no": code,
                "ledger": target_finding.get("module") or "General Ledger (Trial Balance)",
                "party_name": "Double-Entry Balance Variance" if "DET-001" in code else (target_finding.get("category") or "Statutory Compliance"),
                "amount_formatted": diff_str,
                "severity": sev,
                "title": title,
                "description": desc,
                "reason": target_finding.get("reason") or desc,
                "recommended_action": rec,
                "rule": rule,
                "expected_value": expected,
                "actual_value": actual
            }
            evidence_list = [evidence_item]

        return {
            "query": query,
            "intent": "CREATE_AUDIT_OBSERVATION",
            "response": memo.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "finding_id": target_finding.get("id"),
                "wp_reference": f"WP-{code.replace('-', '_')}",
                "severity": sev,
                "statutory_statute": fw["statute"],
                "statutory_disclosure": fw["statutory_disclosure"]
            },
            "evidence": evidence_list,
            "source_transactions": matched_txs or self.transactions[:5],
            "suggested_actions": [
                "Insert memorandum into Working Papers module",
                "Copy to Management Representation Letter draft",
                "Assign to Audit Senior for client inquiry"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 9: Summarize Financial Movement
    # ----------------------------------------------------------------------
    def _handle_financial_movement(self, query: str) -> Dict[str, Any]:
        yoy = run_yoy_comparison(self.engagement_id, threshold_pct=10.0)
        fin_analysis = run_financial_statement_analysis(self.engagement_id)

        summary = yoy.get("summary", {})
        ratios = fin_analysis.get("ratios", {})

        rev_growth = summary.get("revenue_growth_pct", 0.0)
        exp_growth = summary.get("expense_growth_pct", 0.0)
        gm_cy = summary.get("gross_margin_cy", 0.0)
        gm_py = summary.get("gross_margin_py", 0.0)

        cy_fy = yoy.get("current_financial_year", "CY")
        py_fy = yoy.get("previous_financial_year", "PY")

        cr = ratios.get("current_ratio", {}).get("current_year", 0.0)
        qr = ratios.get("quick_ratio", {}).get("current_year", 0.0)
        de = ratios.get("debt_equity_ratio", {}).get("current_year", 0.0)
        npm = ratios.get("net_profit_margin", {}).get("current_year", 0.0)

        narrative = f"""### 📊 Client Financial Performance & Movement Summary
**Client:** {self.client_info.get('name')} | **Entity Type:** {self.client_info.get('entity_type', 'Company')}
**Comparative Period:** {py_fy} vs {cy_fy}

#### 1. Operating Performance & Profitability:
- **Revenue Growth:** Total Revenue moved by **{rev_growth:+.1f}%** YoY.
- **Expenditure Trend:** Total Expenses shifted by **{exp_growth:+.1f}%** YoY.
- **Gross Profit Margin:** Recorded at **{gm_cy:.1f}%** in {cy_fy} (compared to **{gm_py:.1f}%** in {py_fy}).
- **Net Profit Margin:** Assessed at **{npm:.1f}%**.

#### 2. Liquidity & Solvency Health:
- **Current Ratio:** **{cr:.2f}x** (Standard Benchmark: 1.33x - 2.0x) — {'Adequate working capital buffer' if cr >= 1.33 else 'Tight working capital posture'}.
- **Quick Ratio:** **{qr:.2f}x** (Liquidity excluding inventory).
- **Debt-to-Equity:** **{de:.2f}x** (Financial leverage profile).

#### 3. Auditor Analytical Review Remarks:
- Overall operational trajectory demonstrates **{'expansion' if rev_growth > 0 else 'contraction'}**.
- Review required for ledger accounts breaching the 10% tolerance threshold.
"""

        evidence = yoy.get("executive_comparison", [])

        return {
            "query": query,
            "intent": "FINANCIAL_MOVEMENT",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "revenue_growth_pct": rev_growth,
                "expense_growth_pct": exp_growth,
                "gross_margin_cy": gm_cy,
                "current_ratio": cr,
                "debt_equity": de
            },
            "evidence": evidence[:8],
            "source_transactions": self.transactions[:10],
            "suggested_actions": [
                "Document Analytical Review under SA 520 in permanent file",
                "Verify inventory valuation basis for Gross Margin consistency",
                "Perform subsequent sales realization checks"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 10: Cash Limits (40A(3) / 269ST)
    # ----------------------------------------------------------------------
    def _handle_cash_limits(self, query: str) -> Dict[str, Any]:
        cash_txs = [t for t in self.transactions if 'cash' in str(t.get('ledger') or '').lower() or 'cash' in str(t.get('description') or '').lower()]
        total_cash = sum(float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0) for t in cash_txs)
        
        sec_40a3 = [t for t in cash_txs if float(t.get('debit') or t.get('amount') or 0.0) > 10000.0]
        sec_269st = [t for t in cash_txs if float(t.get('credit') or t.get('amount') or 0.0) >= 200000.0]

        narrative = f"""### 💵 Cash Transactions & Statutory Limits Audit
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})

- **Total Cash Ledger Entries:** {len(cash_txs)} transactions
- **Total Cash Turnover:** ₹{total_cash:,.2f}
- **Section 40A(3) Violations (Payments > ₹10,000/day):** **{len(sec_40a3)}** entries
- **Section 269ST Violations (Receipts ≥ ₹2,00,000):** **{len(sec_269st)}** entries

#### 🚨 Flagged Statutory Exceptions:
"""
        evidence = []
        for t in (sec_40a3 + sec_269st)[:8]:
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            is_40a = amt > 10000 and float(t.get('debit') or 0) > 0
            rule_name = "Section 40A(3) (Clause 21(d) Form 3CD)" if is_40a else "Section 269ST (Clause 31 Form 3CD)"
            narrative += f"- **Voucher {t.get('voucher_no')}:** Date: {t.get('date')} | Party: {t.get('party_name') or 'Direct'} | Amount: ₹{amt:,.2f} — *{rule_name}*\n"
            evidence.append({
                "id": t.get("id"),
                "date": t.get("date"),
                "voucher_no": t.get("voucher_no"),
                "ledger": t.get("ledger"),
                "party_name": t.get("party_name") or "Direct",
                "amount": amt,
                "amount_formatted": f"₹{amt:,.2f}",
                "rule_or_pattern": rule_name,
                "reason": f"Violates statutory threshold of {'₹10,000' if is_40a else '₹2,00,000'} in cash mode."
            })

        if not sec_40a3 and not sec_269st:
            narrative += "- All examined cash entries comply with statutory limits under Sections 40A(3) and 269ST.\n"

        return {
            "query": query,
            "intent": "CASH_STATUTORY_LIMITS",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_cash_txs": len(cash_txs),
                "total_cash_volume": total_cash,
                "sec_40a3_count": len(sec_40a3),
                "sec_269st_count": len(sec_269st)
            },
            "evidence": evidence,
            "source_transactions": sec_40a3 + sec_269st,
            "suggested_actions": [
                "Include disallowance details in Tax Audit Report Form 3CD Clause 21(d)",
                "Obtain management explanation regarding banking channel availability",
                "Verify Rule 6DD exception applicability"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 11: Largest Transactions
    # ----------------------------------------------------------------------
    def _handle_largest_transactions(self, query: str) -> Dict[str, Any]:
        sorted_txs = sorted(self.transactions, key=lambda t: float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0), reverse=True)
        top_txs = sorted_txs[:8]

        narrative = f"""### 💎 Highest Value Ledger Transactions
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})

Top {len(top_txs)} transactions by value in the general ledger:

"""
        evidence = []
        for idx, t in enumerate(top_txs, 1):
            amt = float(t.get('amount') or t.get('debit') or t.get('credit') or 0.0)
            dr_cr = "Debit" if float(t.get("debit") or 0.0) > 0 else "Credit"
            narrative += f"{idx}. **Voucher {t.get('voucher_no')}:** Date: {t.get('date')} | Ledger: `{t.get('ledger')}` | Party: {t.get('party_name') or 'Direct'} | **Amount:** ₹{amt:,.2f} ({dr_cr})\n"
            evidence.append({
                "id": t.get("id"),
                "date": t.get("date"),
                "voucher_no": t.get("voucher_no"),
                "invoice_no": t.get("invoice_no") or "—",
                "ledger": t.get("ledger"),
                "party_name": t.get("party_name") or "Direct",
                "amount": amt,
                "amount_formatted": f"₹{amt:,.2f}",
                "type": dr_cr,
                "description": t.get("description")
            })

        return {
            "query": query,
            "intent": "LARGEST_TRANSACTIONS",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "top_transaction_amount": float(top_txs[0].get("amount") or 0.0) if top_txs else 0.0
            },
            "evidence": evidence,
            "source_transactions": top_txs,
            "suggested_actions": [
                "Select all top 5 transactions for mandatory substantive test of details (SA 500)",
                "Inspect contractual agreements for large capital or raw material contracts"
            ]
        }

    # ----------------------------------------------------------------------
    # INTENT HANDLER 12: General Audit Query & Overview
    # ----------------------------------------------------------------------
    def _handle_general_query(self, query: str) -> Dict[str, Any]:
        total_debit = sum(float(t.get("debit") or 0.0) for t in self.transactions)
        total_credit = sum(float(t.get("credit") or 0.0) for t in self.transactions)
        tracked_ledgers = getattr(self, "distinct_ledgers_count", len(self.ledgers))

        narrative = f"""### 🤖 FinAuditPro Local AI Assistant
**Engagement:** {self.engagement.get('title')} ({self.engagement.get('financial_year')})
**Client:** {self.client_info.get('name', 'Client')}

I am your **100% offline, local AI audit assistant**. I analyze your imported financial records deterministically without sending any data over the internet.

#### Current Engagement Snapshot:
- **Total Transactions Loaded:** {len(self.transactions):,}
- **Total Turnover:** ₹{total_debit:,.2f} Dr / ₹{total_credit:,.2f} Cr
- **Active Exceptions & Findings:** {len(self.findings)}
- **Ledger Accounts Tracked:** {tracked_ledgers}

#### 💡 You can ask me specific questions like:
- 🔎 *"Show me unusual transactions."*
- ❓ *"Why was this transaction flagged?"*
- 📈 *"Which ledgers have the largest year-on-year changes?"*
- 🏦 *"Show unmatched bank transactions."*
- 📑 *"Summarize the major audit exceptions."*
- 📋 *"Which accounts require review?"*
- ⚖️ *"Explain this reconciliation difference."*
- 📝 *"Create an audit observation from this finding."*
- 📊 *"Summarize this client's financial movement."*
"""
        return {
            "query": query,
            "intent": "GENERAL_AUDIT_QUERY",
            "response": narrative.strip(),
            "disclaimer": MANDATORY_DISCLAIMER,
            "calculated_metrics": {
                "total_transactions": len(self.transactions),
                "total_findings": len(self.findings),
                "tracked_ledgers": tracked_ledgers,
                "total_debit": total_debit,
                "total_credit": total_credit
            },
            "evidence": self.findings[:5],
            "source_transactions": self.transactions[:10],
            "suggested_actions": [
                "Run Anomaly Detection Engine",
                "Execute Bank and GST Reconciliation",
                "Review Year-on-Year Financial Comparison"
            ]
        }
