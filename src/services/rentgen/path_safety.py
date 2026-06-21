"""Shared path confinement for caller-supplied filesystem inputs.

The analyzer endpoints (Lock Radar, Platform Doctor, Extension Safety, Intake,
Rights/RLS, Performer) accept a path to a 1C configuration or technology journal
and read it. Without confinement that is an arbitrary-file-read / path-traversal
/ existence-oracle vector — even for an authenticated caller, the file content is
reflected back in the response.

``confine_path`` resolves the path and requires it to live under an allowed root.
Allowed roots default to the repo's ``data/``, ``logs/``, ``tests/`` dirs and the
OS temp dir, and can be extended via env ``RENTGEN_ALLOWED_DATA_ROOTS``
(os.pathsep-separated) so an operator can point the tool at where their configs
actually live — while ``C:\\Windows``, ``C:\\Users\\...\\secrets``, ``/etc`` etc.
stay out of reach.

``collect_files`` is a bounded, symlink-safe recursive walk so a huge or hostile
tree cannot DoS the analyzer or silently truncate into a fabricated ``count = 0``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def allowed_roots() -> list[Path]:
    """Resolved roots a caller-supplied path may live under."""
    roots: list[Path] = []
    for part in os.getenv("RENTGEN_ALLOWED_DATA_ROOTS", "").split(os.pathsep):
        part = part.strip()
        if part:
            try:
                roots.append(Path(part).resolve())
            except (OSError, RuntimeError):
                pass
    for sub in ("data", "logs", "tests"):
        try:
            roots.append((_REPO_ROOT / sub).resolve())
        except (OSError, RuntimeError):
            pass
    try:
        roots.append(Path(tempfile.gettempdir()).resolve())
    except (OSError, RuntimeError):
        pass
    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def confine_path(raw, *, label: str = "path", roots: list[Path] | None = None) -> Path:
    """Resolve ``raw`` and require it under an allowed root; else raise ValueError.

    Rejects empty input, absolute paths and ``..`` traversal that escape the
    allowed roots. Returns the resolved, confined :class:`Path`.
    """
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"Empty {label}.")
    try:
        resolved = Path(raw).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Invalid {label}: {raw!r} ({exc}).") from exc
    for root in (roots if roots is not None else allowed_roots()):
        try:
            if resolved == root or resolved.is_relative_to(root):
                return resolved
        except (OSError, RuntimeError):
            continue
    raise ValueError(
        f"Refusing {label} outside the allowed data roots: {raw!r}. "
        f"Place the input under the repo data/ dir or set RENTGEN_ALLOWED_DATA_ROOTS."
    )


def collect_files(
    root: Path,
    *,
    suffixes: set[str] | None = None,
    max_files: int = 50_000,
) -> tuple[list[Path], bool]:
    """Bounded, symlink-safe recursive file collection.

    Returns ``(files, truncated)``. ``truncated`` is True if the cap was hit —
    callers MUST surface that as "unknown", never as a definite ``0``/complete
    count (that would be a fabricated safe-zero). Symlinked directories are not
    followed (``os.walk(followlinks=False)``).
    """
    files: list[Path] = []
    suffixes_l = {s.lower() for s in suffixes} if suffixes is not None else None
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for fn in filenames:
            if suffixes_l is not None and Path(fn).suffix.lower() not in suffixes_l:
                continue
            files.append(Path(dirpath) / fn)
            if len(files) >= max_files:
                return files, True
    return files, False
