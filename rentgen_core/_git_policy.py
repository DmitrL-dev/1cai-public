"""One explicit repository exception in child argv; no persisted Git settings."""

from dataclasses import dataclass
import os
from pathlib import Path
import unicodedata

from .errors import CoreError


def _invalid():
    return CoreError("GIT_TRUST_CONTEXT", "Git permission must match one canonical repository")


@dataclass(frozen=True)
class GitRepositoryTrust:
    """Git ownership exception; caller still owns project authorization and ACLs."""

    repository: Path

    def __post_init__(self):
        root = self.repository
        if not isinstance(root, Path) or not root.is_absolute():
            raise _invalid()
        raw = str(root)
        if any(char in raw for char in "*?%") or any(
            unicodedata.category(char).startswith("C") for char in raw
        ):
            raise _invalid()
        try:
            if root.resolve(strict=True) != root or not root.is_dir():
                raise _invalid()
        except (OSError, RuntimeError) as error:
            raise _invalid() from error


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
        command += ["-c", "safe.directory=", "-c", "safe.directory=" + str(root)]
    return [*command, "-C", str(root), *args]
