"""Bounded source/Git association; not a Git tree proof or analyzer attestation."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .context import SnapshotRef
from .errors import CoreError
from .git_observer import GitObservation

MAX_EVIDENCE_BYTES = 32 * 1024
MAX_EVIDENCE_ROWS = 10000
MAX_EVIDENCE_TOTAL_BYTES = 64 * 1024 * 1024
EVIDENCE_SCHEMA = """CREATE TABLE git_snapshot_evidence (
 commit_id TEXT PRIMARY KEY, evidence TEXT NOT NULL
)"""


def _invalid():
    return CoreError("GIT_SNAPSHOT_EVIDENCE_INVALID", "Invalid Git snapshot evidence")


@dataclass(frozen=True)
class GitSnapshotEvidence:
    """Typed association. Construction alone proves nothing; Observer verifies it."""

    project_id: str
    observation: GitObservation
    snapshot_id: str
    source_digest: str

    def __post_init__(self):
        try:
            SnapshotRef(self.project_id, self.snapshot_id, self.snapshot_id)
            observation = self.observation
            if (
                not isinstance(observation, GitObservation)
                or not isinstance(observation.repository, str)
                or not 1 <= len(observation.repository) <= 4096
                or any(ord(char) < 32 for char in observation.repository)
                or not Path(observation.repository).is_absolute()
                or not isinstance(observation.commit, str)
                or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", observation.commit)
                is None
                or (
                    observation.ref is not None
                    and (
                        not isinstance(observation.ref, str)
                        or not observation.ref.startswith("refs/")
                        or len(observation.ref) > 4096
                        or any(
                            char.isspace() or ord(char) < 32 for char in observation.ref
                        )
                    )
                )
                or not isinstance(self.source_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", self.source_digest) is None
            ):
                raise _invalid()
        except (CoreError, ValueError, TypeError) as exc:
            raise _invalid() from exc


def read_evidence(db, commit):
    """Read one bounded receipt; legacy tables can legitimately be absent."""
    if (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='git_snapshot_evidence'"
        ).fetchone()
        is None
    ):
        return None
    row = db.execute(
        "SELECT evidence FROM git_snapshot_evidence WHERE commit_id=?", (commit,)
    ).fetchone()
    if row is None:
        return None
    try:
        if (
            not isinstance(row[0], str)
            or len(row[0].encode("utf-8")) > MAX_EVIDENCE_BYTES
        ):
            raise _invalid()
        data = json.loads(row[0])
        data["observation"] = GitObservation(**data["observation"])
        result = GitSnapshotEvidence(**data)
        if result.observation.commit != commit:
            raise _invalid()
        return result
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise _invalid() from exc


def save_evidence(db, evidence, raw):
    """Never replace a prior receipt; count and byte limits retain all history."""
    saved = read_evidence(db, evidence.observation.commit)
    if saved is not None:
        if saved != evidence:
            raise CoreError(
                "FINDINGS_REPLAY_CONFLICT", "Conflicting Git snapshot evidence"
            )
        return
    size = len(raw.encode("utf-8"))
    count, used = db.execute(
        "SELECT count(*),coalesce(sum(length(CAST(evidence AS BLOB))),0) FROM git_snapshot_evidence"
    ).fetchone()
    if (
        size > MAX_EVIDENCE_BYTES
        or count >= MAX_EVIDENCE_ROWS
        or used + size > MAX_EVIDENCE_TOTAL_BYTES
    ):
        raise CoreError(
            "OBSERVER_JOURNAL_FULL", "Git evidence limit reached; history retained"
        )
    db.execute(
        "INSERT INTO git_snapshot_evidence(commit_id,evidence) VALUES(?,?)",
        (evidence.observation.commit, raw),
    )
