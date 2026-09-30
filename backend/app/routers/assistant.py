from fastapi import APIRouter, HTTPException
from backend.app.schemas import AssistantQuery
from backend.app.database import get_db_connection
from backend.app.services.local_ai_assistant_engine import LocalAIAssistantEngine, MANDATORY_DISCLAIMER
from backend.app.audit_engine.local_ai import LocalAIAuditAssistant

router = APIRouter(prefix="/api/assistant", tags=["Local AI Assistant"])

@router.post("/query")
def query_assistant(req: AssistantQuery):
    """
    Executes an offline AI query against the selected audit engagement.
    Performs intent detection, deterministic calculations, evidence retrieval, and returns inspectable records.
    """
    try:
        engine = LocalAIAssistantEngine(req.engagement_id)
        result = engine.process_query(
            query=req.query,
            finding_id=req.finding_id,
            transaction_id=req.transaction_id,
            voucher_no=req.voucher_no
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Assistant Error: {str(e)}")

@router.get("/summary/{engagement_id}")
def get_ai_summary(engagement_id: int):
    """
    Returns executive audit summary narrative and risk metrics for the engagement.
    """
    conn = get_db_connection()
    eng_row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if not eng_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Engagement not found")

    engagement = dict(eng_row)
    tx_rows = conn.execute("SELECT * FROM transactions WHERE engagement_id = ?", (engagement_id,)).fetchall()
    transactions = [dict(t) for t in tx_rows]

    findings_rows = conn.execute("SELECT * FROM audit_findings WHERE engagement_id = ?", (engagement_id,)).fetchall()
    findings = [dict(f) for f in findings_rows]
    conn.close()

    assistant = LocalAIAuditAssistant(engagement, transactions, findings)
    summary_data = assistant.generate_audit_summary_narrative()
    summary_data["disclaimer"] = MANDATORY_DISCLAIMER
    return summary_data

@router.get("/suggested-prompts/{engagement_id}")
def get_suggested_prompts(engagement_id: int):
    """
    Returns prompt suggestions for the auditor.
    """
    return {
        "prompts": [
            {
                "title": "Unusual Transactions",
                "query": "Show me unusual transactions.",
                "category": "Anomalies",
                "icon": "alert"
            },
            {
                "title": "Why Flagged?",
                "query": "Why was this transaction flagged?",
                "category": "Drilldown",
                "icon": "help"
            },
            {
                "title": "YoY Ledger Changes",
                "query": "Which ledgers have the largest year-on-year changes?",
                "category": "Analytics",
                "icon": "trending"
            },
            {
                "title": "Bank Exceptions",
                "query": "Show unmatched bank transactions.",
                "category": "Reconciliation",
                "icon": "bank"
            },
            {
                "title": "Audit Exceptions Summary",
                "query": "Summarize the major audit exceptions.",
                "category": "Findings",
                "icon": "document"
            },
            {
                "title": "High Risk Accounts",
                "query": "Which accounts require review?",
                "category": "Planning",
                "icon": "folder"
            },
            {
                "title": "Reconciliation Differences",
                "query": "Explain this reconciliation difference.",
                "category": "Tax & GST",
                "icon": "scale"
            },
            {
                "title": "Create Audit Observation",
                "query": "Create an audit observation from this finding.",
                "category": "Working Papers",
                "icon": "pencil"
            },
            {
                "title": "Financial Movement Summary",
                "query": "Summarize this client's financial movement.",
                "category": "Performance",
                "icon": "chart"
            }
        ],
        "disclaimer": MANDATORY_DISCLAIMER
    }
