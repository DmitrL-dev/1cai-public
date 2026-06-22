"""Рентген local engine — Neo4j-free, SQLite-backed call graph + quality store.

The call graph (730K functions) and module quality scores (26,748 modules) are
ingested once into a single SQLite file (data/rentgen.db) and served in-process.
No Docker, no external graph DB — aligns with the platform's token-free, "code
never leaves the building" thesis.
"""

from .store import DB_PATH, RentgenStore, get_store

__all__ = ["RentgenStore", "get_store", "DB_PATH"]
