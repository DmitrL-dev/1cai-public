"""Shared accessor for the local Рентген SQLite store (Neo4j-free).

The platform has no Docker/Neo4j on target hosts, so the call graph + quality
scores are served from an in-process SQLite store (tools/rentgen). This module
puts tools/ on the path and exposes a safe accessor that returns None when the
store has not been built yet, so endpoints can degrade gracefully instead of
raising 500s.
"""

import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from rentgen.store import RentgenStore, get_store  # noqa: E402

__all__ = ["store_or_none", "get_store", "RentgenStore"]


def store_or_none() -> RentgenStore | None:
    """Return the built store, or None if data/rentgen.db is missing."""
    try:
        s = get_store()
        return s if s.available() else None
    except FileNotFoundError:
        return None
