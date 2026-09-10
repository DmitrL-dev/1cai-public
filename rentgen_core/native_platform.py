"""Local, explicit native compiler process. Never starts the user application."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time

from .errors import CoreError


CONTEXTS = (
    "-Server",
    "-ExternalConnection",
    "-ThinClient",
    "-ThickClientManagedApplication",
)
MAX_LOG = 128 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def command_line(arguments):
    # Native 1C uses doubled quotes, not Windows CRT backslash quoting.
    return " ".join(
        '"' + arg.replace('"', '""') + '"'
        if any(c.isspace() or c == '"' for c in arg)
        else arg
        for arg in map(str, arguments)
    )


@dataclass(frozen=True)
class NativePlatform:
    executable: Path
    executable_sha256: str

    def __post_init__(self):
        if (
            not isinstance(self.executable, Path)
            or self.executable.name.lower() != "1cv8.exe"
            or not isinstance(self.executable_sha256, str)
            or not re.fullmatch("[0-9a-f]{64}", self.executable_sha256)
        ):
            raise CoreError(
                "PLATFORM_PROFILE_INVALID", "Full client path and SHA256 required"
            )

    def invoke(self, folder, name, args, authorize, deadline):
        if os.name != "nt":
            raise CoreError(
                "CAPTURE_PLATFORM_UNSUPPORTED", "Native checks require Windows"
            )
        authorize()
        if time.monotonic() >= deadline:
            raise CoreError("PLATFORM_TIMEOUT", "Native check deadline exceeded")
        log = folder / (name + ".log")
        stdout, stderr = folder / (name + ".stdout"), folder / (name + ".stderr")
        arguments = [
            self.executable,
            *args,
            "/DisableStartupDialogs",
            "/DisableStartupMessages",
            "/Out",
            log,
        ]
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        started = time.monotonic()
        with stdout.open("xb") as out, stderr.open("xb") as err:
            child = subprocess.Popen(
                command_line(arguments),
                executable=str(self.executable),
                startupinfo=startup,
                stdout=out,
                stderr=err,
            )
            try:
                while child.poll() is None:
                    authorize()
                    if time.monotonic() >= min(deadline, started + 120):
                        raise CoreError(
                            "PLATFORM_TIMEOUT", "Native command exceeded deadline"
                        )
                    if any(
                        p.exists() and p.stat().st_size > MAX_LOG
                        for p in (log, stdout, stderr)
                    ):
                        raise CoreError(
                            "PLATFORM_OUTPUT_LIMIT", "Native log exceeds 128 KiB"
                        )
                    try:
                        child.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                if child.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    child.wait(timeout=15)
        authorize()
        outputs = []
        for path in (log, stdout, stderr):
            if not path.is_file() or path.stat().st_size > MAX_LOG:
                raise CoreError(
                    "PLATFORM_OUTPUT_INVALID", "Native log missing or oversized"
                )
            with path.open("rb") as stream:
                raw = stream.read(MAX_LOG + 1)
            if len(raw) > MAX_LOG:
                raise CoreError("PLATFORM_OUTPUT_LIMIT", "Native log exceeds 128 KiB")
            outputs.append(raw)
        try:
            text = outputs[0].decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = outputs[0].decode("cp1251")
            except UnicodeDecodeError as exc:
                raise CoreError(
                    "PLATFORM_OUTPUT_INVALID", "Unsupported native log encoding"
                ) from exc
        return {
            "name": name,
            "exit_code": child.returncode,
            "log": text,
            "log_sha256": digest(outputs[0]),
            "stdout_sha256": digest(outputs[1]),
            "stderr_sha256": digest(outputs[2]),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }

    def check(self, before, after, target, run, authorize):
        """Trusted materialized inputs remain pinned by the caller throughout."""
        deadline = time.monotonic() + 600
        base = run / "infobase"
        steps = []

        def invoke(name, args, *, compiler=False):
            step = self.invoke(run, name, args, authorize, deadline)
            steps.append(step)
            if step["exit_code"] not in ({0, 101} if compiler else {0}):
                raise CoreError(
                    "PLATFORM_COMMAND_FAILED",
                    "Native command failed",
                    details={"stage": name, "exit_code": step["exit_code"]},
                )
            return step

        invoke("create", ["CREATEINFOBASE", f'File="{base}";Locale=ru_RU;'])
        if not (base / "1Cv8.1CD").is_file():
            raise CoreError(
                "PLATFORM_BASE_MISSING", "Native client did not create the test base"
            )
        results = {}
        for phase, source in (("baseline", before), ("candidate", after)):
            common = ["DESIGNER", "/F", base]
            invoke(phase + "-load", [*common, "/LoadConfigFromFiles", source])
            restored = run / (phase + "-roundtrip")
            restored.mkdir()
            invoke(phase + "-dump", [*common, "/DumpConfigToFiles", restored])
            actual = restored / target
            expected = (source / target).read_bytes()
            if not actual.is_file():
                raise CoreError(
                    "PLATFORM_TARGET_NOT_LOADED", "Module missing from native export"
                )
            from ._windows_source_tree import read_retained

            raw = read_retained(actual, 2 * 1024 * 1024)

            def normalize(value):
                return value.decode("utf-8-sig").replace("\r\n", "\n")

            if normalize(raw) != normalize(expected):
                raise CoreError(
                    "PLATFORM_TARGET_MISMATCH",
                    "Native module differs from supplied bytes",
                )
            step = invoke(
                phase + "-check", [*common, "/CheckConfig", *CONTEXTS], compiler=True
            )
            results[phase] = {
                "status": "passed" if step["exit_code"] == 0 else "diagnostics_present",
                "native_module_sha256": digest(raw),
                "module_text_verified": True,
            }
        return {**results, "contexts": list(CONTEXTS), "steps": steps}
