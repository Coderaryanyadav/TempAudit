"""
Assistant Intent Matcher for FinAuditPro Local AI Assistant.
Provides offline natural language query intent classification using audited pattern matching.
Zero external dependencies (pure Python regex).
"""

import re
from typing import List

# =========================================================================
# Intent Constants
# =========================================================================

INTENT_EXPLAIN_FLAGGED_TRANSACTION = "EXPLAIN_FLAGGED_TRANSACTION"
INTENT_UNUSUAL_TRANSACTIONS = "UNUSUAL_TRANSACTIONS"
INTENT_FINANCIAL_MOVEMENT = "FINANCIAL_MOVEMENT"
INTENT_YOY_CHANGES = "YOY_CHANGES"
INTENT_UNMATCHED_BANK = "UNMATCHED_BANK"
INTENT_SUMMARIZE_EXCEPTIONS = "SUMMARIZE_EXCEPTIONS"
INTENT_ACCOUNTS_REQUIRE_REVIEW = "ACCOUNTS_REQUIRE_REVIEW"
INTENT_EXPLAIN_RECONCILIATION = "EXPLAIN_RECONCILIATION"
INTENT_CREATE_AUDIT_OBSERVATION = "CREATE_AUDIT_OBSERVATION"
INTENT_CASH_STATUTORY_LIMITS = "CASH_STATUTORY_LIMITS"
INTENT_LARGEST_TRANSACTIONS = "LARGEST_TRANSACTIONS"
INTENT_GENERAL_AUDIT_QUERY = "GENERAL_AUDIT_QUERY"

ALL_INTENTS: List[str] = [
    INTENT_EXPLAIN_FLAGGED_TRANSACTION,
    INTENT_UNUSUAL_TRANSACTIONS,
    INTENT_FINANCIAL_MOVEMENT,
    INTENT_YOY_CHANGES,
    INTENT_UNMATCHED_BANK,
    INTENT_SUMMARIZE_EXCEPTIONS,
    INTENT_ACCOUNTS_REQUIRE_REVIEW,
    INTENT_EXPLAIN_RECONCILIATION,
    INTENT_CREATE_AUDIT_OBSERVATION,
    INTENT_CASH_STATUTORY_LIMITS,
    INTENT_LARGEST_TRANSACTIONS,
    INTENT_GENERAL_AUDIT_QUERY,
]


def detect_intent(query: str) -> str:
    """
    Identifies the semantic audit intent from the user query using robust pattern matching.
    Pure function with zero database or framework coupling.
    """
    q = (query or "").strip().lower()

    # 1. Why was transaction flagged / explain transaction
    if re.search(r'\b(why|explain|reason)\b.*\b(flagged|flag|voucher|transaction|invoice|entry|item)\b', q) or \
       re.search(r'\b(voucher|v-\d+|inv-\d+|tx-\d+)\b', q) or \
       "why is" in q or "why was" in q:
        return INTENT_EXPLAIN_FLAGGED_TRANSACTION

    # 2. Unusual transactions / Anomalies / Outliers
    if re.search(r'\b(unusual|anomal|anomalies|outlier|outliers|suspicious|flagged|irregular|abnormal)\b', q) or \
       "high risk voucher" in q or "unusual transaction" in q or "anomaly detection" in q:
        return INTENT_UNUSUAL_TRANSACTIONS

    # 3. Summarize financial movement / Financial health
    if re.search(r'\b(financial movement|financial health|performance|p&l|balance sheet|profitability|financial summary)\b', q) or \
       "summarize this client" in q or "client's financial" in q:
        return INTENT_FINANCIAL_MOVEMENT

    # 4. Year-on-Year changes / Variances
    if re.search(r'\b(year-on-year|year on year|yoy|annual change|varianc|growth|largest change|biggest change)\b', q) or \
       "which ledgers have the largest" in q or "compare years" in q or "largest movements" in q or "yoy movement" in q:
        return INTENT_YOY_CHANGES

    # 5. Bank reconciliation / Unmatched bank transactions
    if re.search(r'\b(bank|brs|unmatched bank|unpresented|cheque|deposit in transit|bank charge)\b', q) or \
       "bank reconciliation" in q or "missing in bank" in q or "missing in books" in q:
        return INTENT_UNMATCHED_BANK

    # 6. Summarize audit exceptions / Major findings
    if re.search(r'\b(summarize|summary|overview|breakdown)\b.*\b(exception|exceptions|finding|findings|risk|critical)\b', q) or \
       "major audit exceptions" in q or "key findings" in q or "audit overview" in q:
        return INTENT_SUMMARIZE_EXCEPTIONS

    # 7. Accounts requiring review / High risk ledgers
    if re.search(r'\b(which accounts|accounts require|ledgers require|accounts need|ledgers need|high risk account|suspense|abnormal balance)\b', q) or \
       "require review" in q or "needs review" in q or "which accounts" in q:
        return INTENT_ACCOUNTS_REQUIRE_REVIEW

    # 8. Explain reconciliation difference / GST / Sales-Purchase
    if re.search(r'\b(reconciliation difference|gst mismatch|sales purchase difference|2b mismatch|gstr|reconciliation exception)\b', q) or \
       "explain this reconciliation" in q or "tax difference" in q:
        return INTENT_EXPLAIN_RECONCILIATION

    # 9. Create audit observation / Working paper note
    if re.search(r'\b(create|draft|write|generate)\b.*\b(observation|working paper|note|memo|memorandum|finding)\b', q) or \
       "audit observation" in q or "working paper note" in q:
        return INTENT_CREATE_AUDIT_OBSERVATION

    # 10. Cash limit / Section 40A(3) / 269ST
    if "40a" in q or "269st" in q or "cash" in q:
        return INTENT_CASH_STATUTORY_LIMITS

    # 11. Top / Largest transactions
    if re.search(r'\b(largest|highest|top|biggest)\b.*\b(transaction|voucher|payment|receipt|entry)\b', q):
        return INTENT_LARGEST_TRANSACTIONS

    # 12. Help / Capabilities / Greeting
    if re.search(r'\b(hi|hello|hey|help|guide|assist|capabilities|what can you do|who are you)\b', q):
        return INTENT_GENERAL_AUDIT_QUERY

    return INTENT_GENERAL_AUDIT_QUERY
