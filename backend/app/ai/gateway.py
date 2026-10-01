from typing import Dict, Any, List, Optional
from backend.app.services.local_ai_provider import (
    BaseLocalAIProvider,
    LocalAIModelManager,
    LMStudioProvider,
    BuiltinDeterministicAIProvider
)
from backend.app.ai.context_builder import AIContextBoundary

class AIGateway:
    """
    Central AI Gateway mediating all local LLM interactions, enforcing data boundaries,
    fallback chains, and advisory-only constraints.
    """

    @classmethod
    def get_provider(cls) -> BaseLocalAIProvider:
        return LocalAIModelManager.get_active_provider()

    @classmethod
    def check_health(cls) -> Dict[str, Any]:
        provider = cls.get_provider()
        is_ok, msg, lat = provider.check_health()
        return {
            "engine": provider.get_engine_name(),
            "available": is_ok,
            "status_message": msg,
            "latency_ms": lat
        }

    @classmethod
    def list_models(cls) -> List[str]:
        provider = cls.get_provider()
        return provider.get_available_models()

    @classmethod
    def generate_advisory_analysis(
        cls,
        engagement_id: int,
        client_name: str,
        financial_year: str,
        task_prompt: str,
        relevant_data: Optional[Dict[str, Any]] = None,
        system_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes bounded, privacy-sanitized AI generation for audit advisory analysis.
        Strictly Advisory: Cannot directly modify database state.
        """
        # 1. Build Scoped & Sanitized Context
        context, boundary_meta = AIContextBoundary.build_engagement_context(
            engagement_id=engagement_id,
            client_name=client_name,
            financial_year=financial_year,
            task_type="Advisory Audit Analysis",
            relevant_data=relevant_data
        )

        full_prompt = f"### AUDIT CONTEXT\n{context}\n\n### AUDITOR REQUEST\n{task_prompt}"

        # 2. Query Active Provider with Fallback to Built-in Rule Engine
        provider = cls.get_provider()
        try:
            res = provider.generate(
                prompt=full_prompt,
                system_prompt=system_instructions or "You are FinAuditPro AI Assistant. Provide objective, ICAI standard-compliant audit observations.",
                temperature=0.2
            )
        except Exception:
            # Fallback to Built-in Deterministic Engine
            fallback = BuiltinDeterministicAIProvider()
            res = fallback.generate(prompt=full_prompt)

        return {
            "analysis": res.get("text", ""),
            "engine": res.get("engine", "Unknown"),
            "model": res.get("model", ""),
            "latency_ms": res.get("latency_ms", 0.0),
            "is_advisory_only": True,
            "boundary_meta": boundary_meta
        }
