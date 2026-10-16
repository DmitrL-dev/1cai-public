"""One explicit repository exception in child argv; no persisted Git settings."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

from .errors import CoreError

MAX_GIT_EXECUTABLE_BYTES = 256 * 1024 * 1024


def _invalid():
    return CoreError("GIT_TRUST_CONTEXT", "Git permission must match one canonical repository")


def _canonical(path, *, directory):
    if not isinstance(path, Path) or not path.is_absolute():
        raise _invalid()
    raw = str(path)
    if any(char in raw for char in "*?%") or any(
        unicodedata.category(char).startswith("C") for char in raw
    ):
        raise _invalid()
    try:
        if path.resolve(strict=True) != path or not (
            path.is_dir() if directory else path.is_file()
        ):
            raise _invalid()
    except (OSError, RuntimeError) as error:
        raise _invalid() from error


@dataclass(frozen=True)
class GitRepositoryTrust:
    """Git ownership exception; caller still owns project authorization and ACLs.

    ``executable`` plus ``executable_sha256`` optionally pin the exact Git
    program. Every trusted command re-hashes that file before returning argv,
    so a changed program is refused before it can run. Only this one file is
    pinned; its DLLs, helpers and the hash-to-spawn interval are not.
    """

    repository: Path
    executable: Path | None = None
    executable_sha256: str | None = None

    def __post_init__(self):
        _canonical(self.repository, directory=True)
        if (self.executable is None) != (self.executable_sha256 is None):
            raise _invalid()
        if self.executable is not None:
            _canonical(self.executable, directory=False)
            if (
                type(self.executable_sha256) is not str
                or re.fullmatch("[0-9a-f]{64}", self.executable_sha256) is None
            ):
                raise _invalid()


def _executable_mismatch():
    return CoreError("GIT_EXECUTABLE_MISMATCH", "Pinned Git executable changed")


def _verify_executable(trust):
    """Hash the pinned program immediately before each trusted command."""
    path = trust.executable
    digest = hashlib.sha256()
    try:
        if path.resolve(strict=True) != path:
            raise _executable_mismatch()
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_GIT_EXECUTABLE_BYTES:
                raise _executable_mismatch()
            size = 0
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_GIT_EXECUTABLE_BYTES:
                    raise _executable_mismatch()
                digest.update(chunk)
    except (OSError, RuntimeError) as error:
        raise _executable_mismatch() from error
    if digest.hexdigest() != trust.executable_sha256:
        raise _executable_mismatch()
    return str(path)


def git_environment(inherited=None):
    env = {key: value for key, value in (os.environ if inherited is None else inherited).items()
        if not key.upper().startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
        GIT_NO_REPLACE_OBJECTS="1")
    return env


def git_command(repository, *args, trust=None):
    root = Path(repository).resolve()
    command = ["git", "--no-pager", "-c", "core.fsmonitor=false"]
    if trust is not None:
        if type(trust) is not GitRepositoryTrust or root != trust.repository:
            raise _invalid()
        if trust.executable is not None:
            command[0] = _verify_executable(trust)
        command += ["-c", "safe.directory=", "-c", "safe.directory=" + str(root)]
    return [*command, "-C", str(root), *args]
