"""Bounded, explicit SCM installation adapter; not a Windows service daemon."""

import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from .errors import CoreError


_CREDENTIAL = re.compile(
    r"password|passwd|secret|token|credential|api[-_]?key|bearer", re.I
)
_OPERATIONS = frozenset(
    {"install", "update", "start", "stop", "uninstall", "query", "status"}
)
_PYTHON_EXECUTABLES = frozenset({"python.exe", "pythonw.exe"})
_PYTHON_SERVICE_ARGUMENTS = (
    "-I",
    "-m",
    "rentgen_core.service_entry",
    "--service",
    "--config",
)


def _invalid():
    return CoreError(
        "SERVICE_SPEC_INVALID", "Invalid service installation specification"
    )


def _text(value, limit):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= limit
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or _CREDENTIAL.search(value)
    ):
        raise _invalid()
    return value


def _local_path(raw, suffix):
    raw = _text(raw, 240)
    win = PureWindowsPath(raw)
    if (
        raw.startswith(("\\\\", "//"))
        or any(char in raw for char in '<>"|?*%')
        or ":" in raw[2:]
        or ".." in win.parts
        or any(part.endswith((" ", ".")) for part in win.parts)
    ):
        raise _invalid()
    path = Path(raw)
    if not path.is_absolute() or path.suffix.lower() != suffix:
        raise _invalid()
    return path


def _file(value, suffix):
    if not isinstance(value, (str, Path)):
        raise _invalid()
    path = _local_path(str(value), suffix)
    try:
        if not path.is_file():
            raise _invalid()
        resolved = path.resolve(strict=True)
        if not _local_path(str(resolved), suffix).is_file():
            raise _invalid()
    except (OSError, ValueError, RuntimeError):
        raise _invalid() from None
    return str(resolved)


@dataclass(frozen=True)
class ServiceInstallSpec:
    """Only public names, a local EXE and optional public JSON configuration path.

    No arbitrary argument or service-account credential channel is supported.
    Configuration contents are never read, copied or placed on a command line.
    """

    service_name: str
    display_name: str
    executable: str | Path
    arguments: tuple[str, ...] = ()

    def __post_init__(self):
        name = _text(self.service_name, 80)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name):
            raise _invalid()
        display = _text(self.display_name, 120)
        if not re.fullmatch(r"[\w .()-]+", display) or display != display.strip():
            raise _invalid()
        executable = _file(self.executable, ".exe")
        python_source = Path(self.executable).name.lower() in _PYTHON_EXECUTABLES
        python_target = Path(executable).name.lower() in _PYTHON_EXECUTABLES
        object.__setattr__(self, "executable", executable)
        args = self.arguments
        if type(args) is not tuple or len(args) > 6:
            raise _invalid()
        for arg in args:
            _text(arg, 240)
        if python_source or python_target:
            if (
                not (python_source and python_target)
                or len(args) != 6
                or args[:5] != _PYTHON_SERVICE_ARGUMENTS
            ):
                raise _invalid()
            tail = args[-2:]
        elif len(args) > 3:
            raise _invalid()
        elif args[:1] == ("--service",):
            tail = args[1:]
        else:
            tail = args
        if tail:
            if len(tail) != 2 or tail[0] != "--config":
                raise _invalid()
            config = _file(tail[1], ".json")
            args = args[:-1] + (config,)
        object.__setattr__(self, "arguments", args)

    @property
    def binary_path(self):
        # Always quote the executable, even without spaces, to avoid an unquoted
        # service ImagePath. list2cmdline applies Windows CRT argument escaping.
        result = '"' + self.executable + '"'
        if self.arguments:
            result += " " + subprocess.list2cmdline(self.arguments)
        return result


@dataclass(frozen=True)
class ServiceInstallPlan:
    operation: str
    commands: tuple[tuple[str, ...], ...]
    rollback: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ServiceOperationResult:
    """Acknowledged commands, not proof of completed asynchronous transitions."""

    operation: str
    exists: bool | None = None


class WindowsServiceInstaller:
    """Plan offline, execute explicitly using local sc.exe and finite IO.

    The optional executor follows subprocess.run's signature and must honor the
    supplied timeout. Output is discarded, including localized error text.
    Calls are synchronous and must be serialized by the owner; SCM is not a
    transaction and concurrent external service administration is unsupported.
    """

    def __init__(self, *, executor=None, sc_executable=None, timeout=15.0):
        if (
            type(timeout) not in (float, int)
            or not 0 < timeout <= 60
            or not math.isfinite(timeout)
        ):
            raise _invalid()
        if executor is not None and not callable(executor):
            raise _invalid()
        self._executor = executor if executor is not None else subprocess.run
        self.timeout = float(timeout)
        # No PATH lookup and no PowerShell sc alias. Validate existence only when
        # executing so an offline plan does not need access to the Windows SCM.
        if sc_executable is not None:
            self._sc = _file(sc_executable, ".exe")
        else:
            root = os.environ.get("SystemRoot", r"C:\Windows")
            self._sc = str(Path(root) / "System32" / "sc.exe")

    def plan(self, operation, spec, *, start=False):
        if (
            not isinstance(operation, str)
            or operation not in _OPERATIONS
            or type(spec) is not ServiceInstallSpec
            or type(start) is not bool
            or (start and operation != "install")
        ):
            raise _invalid()
        prefix = (self._sc,)
        query = prefix + ("query", spec.service_name)

        def command(verb):
            return prefix + (verb, spec.service_name)

        config = (
            "binPath=",
            spec.binary_path,
            "DisplayName=",
            spec.display_name,
            "start=",
            "demand",
        )
        rollback = None
        if operation == "install":
            create = (
                command("create")
                + config
                + ("type=", "own", "obj=", r"NT AUTHORITY\LocalService")
            )
            commands = (query, create)
            if start:
                commands += (command("start"),)
                rollback = command("delete")
        elif operation == "update":
            commands = (query, command("config") + config)
        elif operation == "uninstall":
            commands = (query, command("stop"), command("delete"))
        elif operation in {"query", "status"}:
            commands = (query,)
        else:
            commands = (query, command(operation))
        return ServiceInstallPlan(operation, commands, rollback)

    def _ready(self):
        if sys.platform != "win32":
            raise CoreError("SERVICE_PLATFORM_UNSUPPORTED", "Windows SCM is required")
        try:
            _file(self._sc, ".exe")
        except CoreError:
            raise CoreError(
                "SERVICE_SCM_UNAVAILABLE", "Local SCM executable unavailable"
            ) from None

    def _invoke(self, command):
        try:
            result = self._executor(
                list(command),
                shell=False,
                timeout=self.timeout,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            raise CoreError(
                "SERVICE_SCM_TIMEOUT", "SCM command timed out; outcome unknown"
            ) from None
        except Exception:
            raise CoreError(
                "SERVICE_SCM_UNAVAILABLE", "SCM command could not complete"
            ) from None
        code = getattr(result, "returncode", None)
        if type(code) is not int or not 0 <= code <= 0xFFFFFFFF:
            raise CoreError("SERVICE_SCM_PROTOCOL", "Invalid SCM executor result")
        return code

    @staticmethod
    def _check(code, command):
        if code != 0:
            raise CoreError(
                "SERVICE_SCM_FAILED",
                "SCM command rejected",
                details={"operation": command[1], "returncode": code},
            )

    def _operate(self, operation, spec, *, start=False, dry_run=False):
        if type(dry_run) is not bool:
            raise _invalid()
        plan = self.plan(operation, spec, start=start)
        if dry_run:
            return plan
        self._ready()
        # Revalidate files immediately before a mutation that refers to them.
        # Query/start/stop/uninstall can operate after the installed file is gone.
        if operation in {"install", "update"}:
            ServiceInstallSpec(
                spec.service_name, spec.display_name, spec.executable, spec.arguments
            )
        code = self._invoke(plan.commands[0])
        if operation in {"query", "status"}:
            if code not in {0, 1060}:
                self._check(code, plan.commands[0])
            return ServiceOperationResult(operation, exists=code == 0)
        if operation == "install":
            if code == 0:
                raise CoreError("SERVICE_ALREADY_EXISTS", "Service already exists")
            if code != 1060:
                self._check(code, plan.commands[0])
        else:
            self._check(code, plan.commands[0])
        created = False
        try:
            for command in plan.commands[1:]:
                code = self._invoke(command)
                if not (
                    operation == "uninstall" and command[1] == "stop" and code == 1062
                ):
                    self._check(code, command)
                if command[1] == "create":
                    created = True
        except CoreError as error:
            if created and plan.rollback is not None:
                try:
                    rollback_code = self._invoke(plan.rollback)
                    error.details["rollback"] = (
                        "delete_requested" if rollback_code == 0 else "failed"
                    )
                except CoreError:
                    error.details["rollback"] = "failed"
            raise
        return ServiceOperationResult(operation)

    def install(self, spec, *, start=False, dry_run=False):
        return self._operate("install", spec, start=start, dry_run=dry_run)

    def update(self, spec, *, dry_run=False):
        return self._operate("update", spec, dry_run=dry_run)

    def start(self, spec, *, dry_run=False):
        return self._operate("start", spec, dry_run=dry_run)

    def stop(self, spec, *, dry_run=False):
        return self._operate("stop", spec, dry_run=dry_run)

    def uninstall(self, spec, *, dry_run=False):
        return self._operate("uninstall", spec, dry_run=dry_run)

    def query(self, spec, *, dry_run=False):
        return self._operate("query", spec, dry_run=dry_run)

    def status(self, spec, *, dry_run=False):
        return self._operate("status", spec, dry_run=dry_run)
