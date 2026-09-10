"""Bounded local SQLite transactions; every unit of work owns its connection."""

import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .errors import CoreError


@contextmanager
def transaction(path: Path, *, write: bool = False):
    connection = None
    try:
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None
        )
        connection.execute("PRAGMA foreign_keys=ON")
        if not write:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield connection
        connection.commit()
    except sqlite3.Error as exc:
        code = (
            "STATE_BUSY"
            if getattr(exc, "sqlite_errorcode", 0)
            in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
            else "STATE_UNAVAILABLE"
        )
        raise CoreError(code, "Local state transaction failed") from exc
    finally:
        if connection is not None:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


@contextmanager
def create_database(path: Path, schema: str):
    """Own a new DB through schema/bootstrap commit; clean only owned files on error."""
    with path.open("xb"):
        pass
    owned_paths = (path,)
    try:
        sidecars = tuple(
            path.with_name(path.name + suffix)
            for suffix in ("-wal", "-shm", "-journal")
        )
        for sidecar in sidecars:
            if os.path.lexists(sidecar):
                raise FileExistsError(f"Existing SQLite sidecar: {sidecar}")
        # The exclusively reserved DB and its absent sidecars belong to this call.
        owned_paths += sidecars
        with transaction(path, write=True) as connection:
            for statement in schema.split(";"):
                if statement.strip():
                    connection.execute(statement)
            yield connection
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
    except BaseException:
        for owned in owned_paths:
            owned.unlink(missing_ok=True)
        raise
