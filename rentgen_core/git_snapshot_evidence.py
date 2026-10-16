"""Bounded source/Git association with an exact commit-tree blob binding.

Not an analyzer attestation, a temporal atomicity proof or a signed receipt.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess

from ._git_capture import GitOutputLimitExceeded, capture_git
from ._git_policy import git_command, git_environment
from .context import SnapshotRef
from .errors import CoreError
from .git_observer import GitObservation

MAX_EVIDENCE_BYTES = 32 * 1024
MAX_EVIDENCE_ROWS = 10000
MAX_EVIDENCE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_TREE_LISTING_BYTES = 64 * 1024 * 1024
TREE_BINDING_SCHEMA = 1
EVIDENCE_SCHEMA = """CREATE TABLE git_snapshot_evidence (
 commit_id TEXT PRIMARY KEY, evidence TEXT NOT NULL
)"""
_COMMIT_RE = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
_OBJECT_FORMATS = {40: "sha1", 64: "sha256"}
_REGULAR_BLOB_MODES = frozenset({"100644", "100755"})
_LEGACY_KEYS = frozenset({"project_id", "observation", "snapshot_id", "source_digest"})
_BINDING_KEYS = frozenset(
    {
        "schema",
        "object_format",
        "tree",
        "files",
        "git_metadata_files",
        "tree_entries_outside_snapshot",
    }
)


def _invalid():
    return CoreError("GIT_SNAPSHOT_EVIDENCE_INVALID", "Invalid Git snapshot evidence")


def _tree_failed():
    return CoreError("GIT_TREE_PROBE_FAILED", "Git commit tree could not be listed")


def _tree_mismatch(reason):
    return CoreError(
        "GIT_TREE_MISMATCH",
        "Snapshot source bytes differ from the Git commit tree",
        details={"reason": reason},
    )


def _git_metadata(path):
    """The repository's own Git directory or worktree pointer file."""
    return path == ".git" or path.startswith(".git/")


@dataclass(frozen=True)
class GitTreeBinding:
    """Schema 1: every counted snapshot file equals its commit-tree blob.

    ``files`` snapshot files hashed as Git blobs equal regular-file entries at
    the same repository paths of ``tree``. ``git_metadata_files`` were captured
    under the repository's own ``.git`` and are excluded from the comparison.
    ``tree_entries_outside_snapshot`` counts tree entries inside the captured
    layer roots that the snapshot does not contain; they are not proven.
    """

    schema: int
    object_format: str
    tree: str
    files: int
    git_metadata_files: int
    tree_entries_outside_snapshot: int

    def __post_init__(self):
        counts = (self.files, self.git_metadata_files, self.tree_entries_outside_snapshot)
        if (
            type(self.schema) is not int
            or self.schema != TREE_BINDING_SCHEMA
            or type(self.object_format) is not str
            or type(self.tree) is not str
            or re.fullmatch(_COMMIT_RE, self.tree) is None
            or _OBJECT_FORMATS[len(self.tree)] != self.object_format
            or any(type(value) is not int or not 0 <= value < 2**31 for value in counts)
        ):
            raise _invalid()


@dataclass(frozen=True)
class GitSnapshotEvidence:
    """Typed association. Construction alone proves nothing; Observer verifies it.

    ``tree_binding`` is absent only in records saved before schema 1 tree
    binding; such legacy records stay readable but are never written again.
    """

    project_id: str
    observation: GitObservation
    snapshot_id: str
    source_digest: str
    tree_binding: GitTreeBinding | None = None

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
                or re.fullmatch(_COMMIT_RE, observation.commit) is None
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
                or (
                    self.tree_binding is not None
                    and (
                        type(self.tree_binding) is not GitTreeBinding
                        or len(self.tree_binding.tree) != len(observation.commit)
                    )
                )
            ):
                raise _invalid()
        except (CoreError, ValueError, TypeError) as exc:
            raise _invalid() from exc


@dataclass(frozen=True)
class GitTree:
    """Listed entries of one commit tree: path bytes -> (mode, type, object ID)."""

    commit: str
    object_format: str
    tree: str
    entries: dict


def _git(root, args, max_stdout, trust):
    try:
        result = capture_git(
            git_command(root, *args, trust=trust),
            env=git_environment(),
            max_stdout=max_stdout,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired, GitOutputLimitExceeded) as exc:
        raise _tree_failed() from exc
    if result.returncode != 0:
        raise _tree_failed()
    return result.stdout


def read_git_tree(repository, commit, *, trust=None) -> GitTree:
    """List ``commit^{tree}`` through the trusted command policy.

    Reads only Git objects: never the index, working tree or replacement refs.
    """
    if type(commit) is not str or re.fullmatch(_COMMIT_RE, commit) is None:
        raise _tree_failed()
    root = Path(repository).resolve()
    width = len(commit)
    try:
        tree = _git(
            root,
            ("rev-parse", "--verify", "--quiet", commit + "^{commit}^{tree}"),
            8192,
            trust,
        ).decode("ascii", errors="strict").strip()
    except UnicodeError as exc:
        raise _tree_failed() from exc
    if re.fullmatch(f"[0-9a-f]{{{width}}}", tree) is None:
        raise _tree_failed()
    listing = _git(
        root, ("ls-tree", "-r", "-z", "--full-tree", tree), MAX_TREE_LISTING_BYTES, trust
    )
    if listing and not listing.endswith(b"\0"):
        raise _tree_failed()
    entries = {}
    for record in listing.split(b"\0")[:-1]:
        meta, tab, path = record.partition(b"\t")
        fields = meta.split(b" ")
        if not tab or not path or len(fields) != 3 or path in entries:
            raise _tree_failed()
        try:
            mode, kind, oid = (field.decode("ascii", errors="strict") for field in fields)
        except UnicodeError as exc:
            raise _tree_failed() from exc
        if (
            re.fullmatch("[0-7]{6}", mode) is None
            or kind not in ("blob", "commit")
            or re.fullmatch(f"[0-9a-f]{{{width}}}", oid) is None
        ):
            raise _tree_failed()
        entries[path] = (mode, kind, oid)
    return GitTree(commit, _OBJECT_FORMATS[width], tree, entries)


def bind_git_tree(tree, paths, read, roots) -> GitTreeBinding:
    """Bind snapshot files at repository ``paths`` to one listed tree.

    A path outside the repository's own ``.git`` must name a regular blob entry
    whose Git blob ID equals the hash of exactly ``read(path)``. Any missing
    path, non-regular entry, duplicate or content difference fails closed.
    ``roots`` are the captured layer roots relative to the repository root.
    """
    if type(tree) is not GitTree or not callable(read):
        raise _tree_mismatch("context")
    algorithm = hashlib.sha1 if tree.object_format == "sha1" else hashlib.sha256
    bound, metadata = set(), 0
    for path in paths:
        if type(path) is not str:
            raise _tree_mismatch("context")
        if _git_metadata(path):
            metadata += 1
            continue
        key = path.encode("utf-8")
        if key in bound:
            raise _tree_mismatch("duplicate")
        item = tree.entries.get(key)
        if item is None:
            raise _tree_mismatch("missing")
        mode, kind, oid = item
        if kind != "blob" or mode not in _REGULAR_BLOB_MODES:
            raise _tree_mismatch("not_regular_file")
        raw = read(path)
        if type(raw) is not bytes:
            raise _tree_mismatch("context")
        digest = algorithm(b"blob %d\0" % len(raw))
        digest.update(raw)
        if digest.hexdigest() != oid:
            raise _tree_mismatch("content")
        bound.add(key)
    prefixes = []
    for root in roots:
        if type(root) is not str:
            raise _tree_mismatch("context")
        if root == ".":
            prefixes = None
            break
        prefixes.append(root.encode("utf-8") + b"/")
    outside = sum(
        1
        for key in tree.entries
        if key not in bound
        and (prefixes is None or any(key.startswith(prefix) for prefix in prefixes))
    )
    return GitTreeBinding(
        TREE_BINDING_SCHEMA, tree.object_format, tree.tree, len(bound), metadata, outside
    )


def read_evidence(db, commit):
    """Read one bounded receipt; legacy tables can legitimately be absent.

    Records without ``tree_binding`` predate schema 1 tree binding and remain
    readable as such; an unknown or malformed binding version is refused.
    """
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
        if not isinstance(data, dict) or set(data) not in (
            _LEGACY_KEYS,
            _LEGACY_KEYS | {"tree_binding"},
        ):
            raise _invalid()
        data["observation"] = GitObservation(**data["observation"])
        if "tree_binding" in data:
            binding = data["tree_binding"]
            if not isinstance(binding, dict) or set(binding) != _BINDING_KEYS:
                raise _invalid()
            data["tree_binding"] = GitTreeBinding(**binding)
        result = GitSnapshotEvidence(**data)
        if result.observation.commit != commit:
            raise _invalid()
        return result
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise _invalid() from exc


def save_evidence(db, evidence, raw):
    """Never replace a prior receipt; count and byte limits retain all history.

    New receipts must carry the schema 1 tree binding.
    """
    saved = read_evidence(db, evidence.observation.commit)
    if saved is not None:
        if saved != evidence:
            raise CoreError(
                "FINDINGS_REPLAY_CONFLICT", "Conflicting Git snapshot evidence"
            )
        return
    if type(evidence) is not GitSnapshotEvidence or evidence.tree_binding is None:
        raise _invalid()
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
