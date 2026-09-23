"""Plan-only ibcmd file roundtrips for an owned fixture; no process launcher."""
from dataclasses import dataclass, fields, is_dataclass
from pathlib import PureWindowsPath
import re
from uuid import UUID

from .errors import CoreError

SUPPORTED_VERSION = "8.3.27.2342"
HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class IBCmdProfile:
    executable: str
    version: str
    sha256: str


@dataclass(frozen=True)
class FixtureCommandRequest:
    operation_id: str
    input_digest: str


@dataclass(frozen=True)
class FixtureCommand:
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int = 120
    max_output_bytes: int = 2 * 1024**2
    shell: bool = False


@dataclass(frozen=True)
class FixtureCommandPlan:
    operation_id: str
    input_digest: str
    platform_sha256: str
    platform_version: str
    commands: tuple[FixtureCommand, ...]
    execution_allowed: bool = False
    live_apply_allowed: bool = False


def _require(condition):
    if not condition:
        raise CoreError("EDT_COMMAND_INVALID", "Invalid ibcmd fixture command plan")


def _windows_path(value):
    _require(type(value) is str and 1 <= len(value) <= 1024)
    _require(not any(ord(char) < 32 for char in value))
    path = PureWindowsPath(value)
    _require(path.is_absolute() and re.fullmatch(r"[A-Za-z]:", path.drive))
    _require(str(path) == value and len(path.parts) > 1)
    for part in path.parts[1:]:
        _require(part not in {".", ".."} and not part.endswith((" ", ".")))
        _require(not any(char in '<>:"|?*' for char in part))
        _require(not PureWindowsPath(part).is_reserved())
    return path


def plan_fixture_commands(
    profile: IBCmdProfile, request: FixtureCommandRequest, *, fixture_root: str
) -> FixtureCommandPlan:
    """Describe create/import/export; ownership and bytes are not opened or pinned."""
    _require(type(profile) is IBCmdProfile and type(request) is FixtureCommandRequest)
    _require(type(profile.version) is str and profile.version == SUPPORTED_VERSION)
    _require(_windows_path(profile.executable).name.lower() == "ibcmd.exe")
    for digest in (profile.sha256, request.input_digest):
        _require(type(digest) is str and HASH.fullmatch(digest))
    _require(type(request.operation_id) is str)
    try:
        _require(str(UUID(request.operation_id)) == request.operation_id)
    except ValueError as exc:
        raise CoreError(
            "EDT_COMMAND_INVALID", "Invalid ibcmd fixture operation ID"
        ) from exc
    run = _windows_path(fixture_root) / "ibcmd-fixtures" / request.operation_id
    common = (
        f"--data={run / 'data'}",
        f"--db-path={run / 'infobase'}",
    )
    commands = (
        FixtureCommand(
            (profile.executable, "infobase", "create", *common),
            str(run),
        ),
        FixtureCommand(
            (
                profile.executable,
                "config",
                "import",
                *common,
                f"--out={run / 'candidate.cf'}",
                str(run / "input"),
            ),
            str(run),
        ),
        FixtureCommand(
            (
                profile.executable,
                "config",
                "export",
                *common,
                f"--file={run / 'candidate.cf'}",
                "--threads=1",
                str(run / "roundtrip"),
            ),
            str(run),
        ),
    )
    return FixtureCommandPlan(
        request.operation_id,
        request.input_digest,
        profile.sha256,
        profile.version,
        commands,
    )


def _same_typed_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, tuple):
        return len(actual) == len(expected) and all(
            _same_typed_value(left, right) for left, right in zip(actual, expected)
        )
    if is_dataclass(expected):
        return all(
            _same_typed_value(
                getattr(actual, field.name), getattr(expected, field.name)
            )
            for field in fields(expected)
        )
    return actual == expected


def validate_fixture_commands(
    plan: FixtureCommandPlan,
    profile: IBCmdProfile,
    request: FixtureCommandRequest,
    *,
    fixture_root: str,
) -> FixtureCommandPlan:
    """Rebuild against caller-owned intent, without granting execution authority."""
    expected = plan_fixture_commands(profile, request, fixture_root=fixture_root)
    _require(_same_typed_value(plan, expected))
    return expected
