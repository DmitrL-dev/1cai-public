"""LLM providers — honest, read-only status of the OPTIONAL generation layer (public).

IMPORTANT: 1С:Рентген analytics (call graph, impact, risk) are TOKEN-FREE and never call an
LLM. This endpoint reports the optional generation layer's configured providers (from
``config/llm_providers.yaml``) so an operator can see what, if anything, is wired up. It
exposes provider name / type / status / priority ONLY — never API keys, base URLs, or any
other secret. Mounted unauthenticated like ``/health`` because the payload is non-sensitive.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm", tags=["LLM"])


@router.get("/providers")
def llm_providers() -> Dict[str, Any]:
    """List configured optional LLM providers (safe fields only). Read-only."""
    try:
        from src.services.llm_provider_manager import load_llm_provider_manager

        manager = load_llm_provider_manager()
        providers = [
            {
                "name": p.name,
                "type": p.provider_type,
                "priority": p.priority,
                "enabled": p.enabled,
                "status": p.status,
                "self_hosted": p.is_self_hosted,
            }
            for p in sorted(manager.providers.values(), key=lambda x: x.priority)
        ]
        return {
            "providers": providers,
            "total": len(providers),
            "enabled_count": sum(1 for p in providers if p["enabled"]),
            "active": manager.active_provider,
            "configured": manager.has_configuration(),
            "note": (
                "Optional generation layer. 1С:Рентген analytics are token-free and never "
                "call an LLM regardless of this list. Secrets (keys/URLs) are not exposed."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm providers unavailable: %s", exc)
        return {"providers": [], "total": 0, "error": str(exc)}


@router.get("/health")
def llm_health() -> Dict[str, Any]:
    """Liveness only."""
    return {"status": "ok", "service": "llm"}
