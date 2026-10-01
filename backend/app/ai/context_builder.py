import re
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

from backend.app.services.local_ai_provider import sanitize_audit_text

MAX_AI_CONTEXT_CHARS = 12000 # ~3000 tokens limit to prevent context explosion

class AIContextBoundary:
    """
    Enforces strict data scoping, minimization, and privacy boundaries
    before any prompt or context is sent to local AI inference.
    """

    @classmethod
    def build_engagement_context(
        cls,
        engagement_id: int,
        client_name: str,
        financial_year: str,
        task_type: str,
        relevant_data: Optional[Dict[str, Any]] = None,
        max_records: int = 25
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Builds a strictly minimized, redacted context block scoped to the engagement.
        Does NOT dump raw database or untruncated records.
        """
        context_parts = []
        redaction_summary = {}

        # 1. Header Scope
        context_parts.append(f"AUDIT ENGAGEMENT SCOPE: FY {financial_year}")
        context_parts.append(f"TASK TYPE: {task_type}")

        # 2. Selected Data Minimization
        if relevant_data:
            if "transactions" in relevant_data:
                tx_list = relevant_data["transactions"][:max_records]
                context_parts.append(f"\nRELEVANT TRANSACTIONS (Sampled {len(tx_list)} records):")
                for tx in tx_list:
                    # Only include essential fields: Date, Description, Amount, Ledger
                    amt = tx.get("amount", 0.0)
                    desc = tx.get("description", "")
                    ledger = tx.get("ledger", "")
                    dt = tx.get("date", "")
                    context_parts.append(f"- Date: {dt} | Ledger: {ledger} | Amount: ₹{amt} | Desc: {desc[:60]}")

            if "finding" in relevant_data:
                f = relevant_data["finding"]
                context_parts.append(f"\nAUDIT FINDING CONTEXT:")
                context_parts.append(f"- Code: {f.get('finding_code')} | Category: {f.get('category')} | Severity: {f.get('severity')}")
                context_parts.append(f"- Title: {f.get('title')}")
                context_parts.append(f"- Expected: {f.get('expected_value')} | Actual: {f.get('actual_value')}")

            if "reconciliation_summary" in relevant_data:
                r = relevant_data["reconciliation_summary"]
                context_parts.append(f"\nRECONCILIATION SUMMARY:")
                context_parts.append(f"- Type: {r.get('recon_type')} | Unreconciled Amount: ₹{r.get('unreconciled_amount')}")

        raw_context = "\n".join(context_parts)

        # 3. Apply Strict PII & Sensitive Identifiers Redaction
        sanitized_context, red_counts = sanitize_audit_text(raw_context, client_name=client_name)
        
        # 4. Truncate to Max Context Length
        if len(sanitized_context) > MAX_AI_CONTEXT_CHARS:
            sanitized_context = sanitized_context[:MAX_AI_CONTEXT_CHARS] + "\n...[CONTEXT TRUNCATED FOR BOUNDARY ENFORCEMENT]..."

        metadata = {
            "engagement_id": engagement_id,
            "char_count": len(sanitized_context),
            "redactions": red_counts,
            "truncated": len(raw_context) > MAX_AI_CONTEXT_CHARS
        }

        return sanitized_context, metadata
