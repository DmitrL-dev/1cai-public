"""Simple async in-process multi-layer cache compatibility module."""

import time
from typing import Any, Dict, Optional, Tuple


def generate_cache_key(namespace: str, **parts: Any) -> str:
    normalized = [str(namespace)]
    for key in sorted(parts):
        normalized.append(f"{key}:{parts[key]}")
    return "|".join(normalized)


class MultiLayerCache:
    """L1-only async cache that preserves the historical test contract."""

    def __init__(self, redis_client: Any = None) -> None:
        self.redis_client = redis_client
        self._l1: Dict[str, Tuple[Any, Optional[float]]] = {}
        self.hits = {"l1": 0, "l2": 0, "miss": 0}

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._l1[key] = (value, expires_at)

    async def get(self, key: str) -> Any:
        item = self._l1.get(key)
        if item is None:
            self.hits["miss"] += 1
            return None

        value, expires_at = item
        if expires_at is not None and expires_at < time.monotonic():
            self._l1.pop(key, None)
            self.hits["miss"] += 1
            return None

        self.hits["l1"] += 1
        return value


__all__ = ["MultiLayerCache", "generate_cache_key"]
