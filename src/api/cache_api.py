"""Cache metrics — honest, read-only operability endpoint (public).

1С:Рентген serves analytics from the prebuilt SQLite store (``data/rentgen.db``), so the
product path needs no hot runtime cache. This endpoint reports a shared in-process
``MultiLayerCache`` (L1 LRU; Redis/L2 only if configured) with REAL stats — zero until the
cache is exercised, never fabricated, and never exposing any secret. Mounted unauthenticated
like ``/health`` because it discloses only aggregate counters.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cache", tags=["Cache"])

_process_cache: Any = None


def get_process_cache() -> Any:
    """Lazily create ONE shared in-process MultiLayerCache (L1-only unless Redis is set)."""
    global _process_cache
    if _process_cache is None:
        from src.infrastructure.cache.multi_layer import MultiLayerCache

        _process_cache = MultiLayerCache()
    return _process_cache


@router.get("/metrics")
def cache_metrics() -> Dict[str, Any]:
    """Real metrics for the shared in-process cache. Read-only; exposes no secrets."""
    try:
        cache = get_process_cache()
        stats = cache.get_stats()
        payload: Dict[str, Any] = {
            "type": "multi_layer_in_process",
            "redis_enabled": getattr(cache, "redis", None) is not None,
        }
        if isinstance(stats, dict):
            payload.update(stats)
        payload["note"] = (
            "1С:Рентген serves analytics from the prebuilt SQLite store; no hot runtime "
            "cache is required. Stats are real (zero until the cache is exercised)."
        )
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache metrics unavailable: %s", exc)
        return {"type": "unavailable", "error": str(exc)}


@router.get("/health")
def cache_health() -> Dict[str, Any]:
    """Liveness only."""
    return {"status": "ok", "service": "cache"}
