from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging

from backend.app.schemas import (
    AssistantQuery,
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    ChatTurnRequest
)
from backend.app.database import get_db_connection
from backend.app.auth import get_current_user, require_engagement_access
from backend.app.services.local_ai_assistant_engine import LocalAIAssistantEngine, MANDATORY_DISCLAIMER
from backend.app.services.assistant_orchestrator import AssistantOrchestrator
from backend.app.audit_engine.local_ai import LocalAIAuditAssistant

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/assistant", tags=["Local AI Assistant"])


# =========================================================================
# Conversational Thread Management Endpoints
# =========================================================================

@router.get("/conversations/{engagement_id}")
def list_conversations(
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Lists all saved multi-turn conversations for this engagement and authenticated user.
    """
    require_engagement_access(engagement_id, current_user)
    user_id = current_user.get("id") or 1
    return AssistantOrchestrator.get_conversations(engagement_id=engagement_id, user_id=user_id)


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    req: ConversationCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new isolated conversation thread for the active engagement.
    """
    require_engagement_access(req.engagement_id, current_user)
    user_id = current_user.get("id") or 1
    return AssistantOrchestrator.create_conversation(
        engagement_id=req.engagement_id,
        user_id=user_id,
        title=req.title or "New Conversation"
    )


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all messages, tool executions, and evidence references for a specific thread.
    """
    require_engagement_access(engagement_id, current_user)
    conv = AssistantOrchestrator.get_conversation(conversation_id, engagement_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")
    return AssistantOrchestrator.get_messages(conversation_id)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    engagement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes a conversation thread and its associated message history.
    """
    require_engagement_access(engagement_id, current_user)
    deleted = AssistantOrchestrator.delete_conversation(conversation_id, engagement_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "message": "Conversation deleted"}


# =========================================================================
# Multi-Turn Chat Endpoint (Synchronous & Streaming SSE)
# =========================================================================

@router.post("/chat")
def chat_with_assistant(
    req: ChatTurnRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Executes a multi-turn conversational interaction with tool-calling evidence retrieval.
    Supports real-time SSE streaming when stream=true.
    """
    require_engagement_access(req.engagement_id, current_user)
    user_id = current_user.get("id") or 1

    if req.stream:
        return StreamingResponse(
            AssistantOrchestrator.stream_chat_turn(
                engagement_id=req.engagement_id,
                user_id=user_id,
                message=req.message,
                conversation_id=req.conversation_id
            ),
            media_type="text/event-stream"
        )
    else:
        return AssistantOrchestrator.execute_chat_turn(
            engagement_id=req.engagement_id,
            user_id=user_id,
            message=req.message,
            conversation_id=req.conversation_id
        )


# =========================================================================
# Legacy Query & Summary Endpoints (Maintained for 100% Backward Compatibility)
# =========================================================================

@router.post("/query")
def query_assistant(req: AssistantQuery, current_user: dict = Depends(get_current_user)):
    """
    Executes an offline AI query against the selected audit engagement.
    Performs intent detection, deterministic calculations, evidence retrieval, and returns inspectable records.
    """
    require_engagement_access(req.engagement_id, current_user)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI Assistant Query Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the audit assistant query. Please check server logs.")


@router.get("/summary/{engagement_id}")
def get_ai_summary(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns executive audit summary narrative and risk metrics for the engagement.
    """
    require_engagement_access(engagement_id, current_user)
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
def get_suggested_prompts(engagement_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns prompt suggestions for the auditor.
    """
    require_engagement_access(engagement_id, current_user)
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
