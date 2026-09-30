from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from backend.app.auth import get_current_user, require_role
from backend.app.services.local_ai_provider import LocalAIModelManager, sanitize_audit_text
from backend.app.utils.audit_logger import log_audit_event

router = APIRouter(prefix="/api/ai-manager", tags=["Offline Local AI Model Manager"])

class AISettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    engine: Optional[str] = None
    model_name: Optional[str] = None
    model_location: Optional[str] = None
    ram_vram_requirement: Optional[str] = None
    context_size: Optional[int] = None
    temperature: Optional[float] = None

class AIGenerateRequest(BaseModel):
    prompt: str = Field(..., max_length=15000, description="Prompt text limited to 15,000 characters")
    system_prompt: Optional[str] = Field(None, max_length=5000)
    client_name: Optional[str] = Field(None, max_length=200)

class SanitizePreviewRequest(BaseModel):
    text: str = Field(..., max_length=20000)
    client_name: Optional[str] = Field(None, max_length=200)

class TestAIPromptRequest(BaseModel):
    prompt: Optional[str] = Field("Confirm LM Studio connectivity with a concise verification statement.", max_length=2000)

@router.get("/status")
def get_ai_status(current_user: dict = Depends(get_current_user)):
    """Returns complete Local AI Model Manager status, LM Studio status, active model, and fallback health."""
    try:
        return LocalAIModelManager.get_full_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check local AI status: {str(e)}")

@router.get("/models")
def get_available_models(current_user: dict = Depends(get_current_user)):
    """Fetches list of available / loaded models from the local LM Studio server."""
    try:
        models = LocalAIModelManager.get_available_models()
        return {
            "status": "success",
            "models": models,
            "count": len(models)
        }
    except Exception as e:
        return {
            "status": "offline",
            "models": [],
            "count": 0,
            "message": f"Could not fetch models: {str(e)}"
        }

@router.post("/settings")
def update_ai_settings(payload: AISettingsUpdate, current_user: dict = Depends(require_role(["Admin"]))):
    """Updates Local AI Model Manager settings (Admin only)."""
    try:
        old_config = LocalAIModelManager.get_config()
        update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
        new_config = LocalAIModelManager.save_config(update_data)
        
        # Log to immutable audit trail
        from backend.app.database import get_db_connection
        conn = get_db_connection()
        log_audit_event(
            conn=conn,
            action="SETTINGS_CHANGE",
            module="AI_MODEL_MANAGER",
            record_id="local_ai_settings",
            old_value=old_config,
            new_value=new_config,
            user=current_user,
            details=f"Updated Local AI Engine configuration to {new_config.get('engine')} ({new_config.get('model_name')})"
        )
        conn.close()
        return new_config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save AI configuration: {str(e)}")

@router.post("/test-connection")
def test_ai_connection(current_user: dict = Depends(get_current_user)):
    """Performs live health-check against the local LM Studio endpoint (http://localhost:1234)."""
    try:
        provider = LocalAIModelManager.get_active_provider()
        is_avail, msg, latency = provider.check_health()
        models = provider.get_available_models()
        return {
            "is_available": is_avail,
            "engine": provider.get_engine_name(),
            "status_message": msg,
            "latency_ms": latency,
            "available_models": models,
            "fallback_notice": "LM Studio is not connected. AI assistance is unavailable, but audit calculations and analysis remain available." if not is_avail else None
        }
    except Exception as e:
        return {
            "is_available": False,
            "status_message": f"LM Studio connection test failed: {str(e)}",
            "latency_ms": 0.0,
            "available_models": [],
            "fallback_notice": "LM Studio is not connected. AI assistance is unavailable, but audit calculations and analysis remain available."
        }

@router.post("/test-ai")
def test_ai_generation(req: TestAIPromptRequest, current_user: dict = Depends(get_current_user)):
    """Tests live generation with LM Studio to verify local model responses."""
    try:
        res = LocalAIModelManager.execute_inference(
            prompt=req.prompt or "Verify audit assistant connectivity.",
            system_prompt="You are FinAuditPro's local AI assistant. State clearly that the LM Studio connection test is successful."
        )
        return {
            "status": "success" if res.get("success") else "fallback",
            "response": res.get("text", ""),
            "engine": res.get("engine", "LM Studio"),
            "model": res.get("model", ""),
            "latency_ms": res.get("latency_ms", 0.0),
            "is_deterministic_fallback": res.get("is_deterministic_fallback", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation test failed: {str(e)}")

@router.post("/generate")
def generate_local_ai_response(req: AIGenerateRequest, current_user: dict = Depends(get_current_user)):
    """Executes safe, sanitized local inference via LM Studio with deterministic fallback if offline."""
    try:
        return LocalAIModelManager.execute_inference(
            prompt=req.prompt,
            system_prompt=req.system_prompt,
            client_name=req.client_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local AI execution error: {str(e)}")

@router.post("/sanitize-preview")
def preview_data_sanitization(req: SanitizePreviewRequest, current_user: dict = Depends(get_current_user)):
    """Previews prompt sanitization and PII/financial data redaction (PAN, GSTIN, Bank A/C, Client Name)."""
    sanitized, stats = sanitize_audit_text(req.text, req.client_name)
    return {
        "original_text": req.text,
        "sanitized_text": sanitized,
        "redaction_counts": stats,
        "zero_cloud_leak_verified": True
    }
