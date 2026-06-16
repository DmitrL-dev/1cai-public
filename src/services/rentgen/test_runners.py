"""Runner adapters and evidence bundling for 1C test execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event
from src.services.rentgen.test_evidence import import_junit_xml, record_test_run


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE_ROOT = ROOT / "data" / "test_evidence_bundles"
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "test-runners"
DEFAULT_BSL_MANIFEST = ROOT / "tests" / "bsl" / "testplan.json"

# --- Security hardening (RCE / arbitrary-file-read defense-in-depth) ---------
# Test execution spawns OS processes with runner-controlled argv. It is gated
# behind an explicit, default-OFF feature flag so the endpoints cannot spawn
# anything unless an operator has deliberately enabled it on the host.
TEST_EXECUTION_FLAG = "RENTGEN_ENABLE_TEST_EXECUTION"


class TestExecutionDisabled(PermissionError, ValueError):
    """Raised when test execution is refused by the kill switch.

    Subclasses both ``PermissionError`` (so the HTTP layer maps it to 403) and
    ``ValueError`` (so existing MCP/value-based error handlers refuse cleanly
    instead of letting it escape as an unhandled exception).
    """

    # Tell pytest this is not a test class (its name starts with "Test").
    __test__ = False


# Only these executable basenames may ever be spawned. Anything else (a custom
# binary smuggled in via report_path/extra_args/manifest) is refused. The set is
# derived from the legitimate runners the adapters actually invoke plus the
# interpreters our own helper scripts run under.
ALLOWED_EXECUTABLE_BASENAMES = frozenset(
    {
        "python",
        "python3",
        "python.exe",
        "pythonw.exe",
        "oscript",
        "oscript.exe",
        "1cv8",
        "1cv8.exe",
        "1cv8c",
        "1cv8c.exe",
        "vanessa-runner",
        "vanessa-runner.exe",
        "1ctestc",
        "1ctestc.exe",
    }
)

# Caller-supplied filesystem paths that we READ from (a result file to import, a
# test manifest) must resolve inside one of these roots. This confines reads to
# the repository's test/evidence areas plus the OS scratch dir (where CI/test
# runners legitimately write reports) and kills arbitrary file read/traversal of
# sensitive locations (home dirs, repo secrets, /etc, ...).
ALLOWED_PATH_ROOTS = (
    ROOT / "tests",
    ROOT / "output",
    ROOT / "data",
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    Path(tempfile.gettempdir()),
)


def _test_execution_enabled() -> bool:
    return os.getenv(TEST_EXECUTION_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def _executable_basename(command_part: str) -> str:
    # Normalize separators so a Windows path never slips past the basename check.
    return Path(str(command_part).replace("\\", "/")).name.casefold()


def _assert_executable_allowed(command: list[str]) -> None:
    if not command:
        raise ValueError("Refusing to execute an empty command.")
    basename = _executable_basename(command[0])
    if basename not in {item.casefold() for item in ALLOWED_EXECUTABLE_BASENAMES}:
        raise ValueError(
            f"Refusing to execute non-allow-listed runner '{command[0]}'. "
            f"Allowed runners: {sorted(ALLOWED_EXECUTABLE_BASENAMES)}."
        )


def _confine_path(raw: str | os.PathLike[str], *, label: str) -> Path:
    """Resolve a caller-supplied path and confine it under an allowed root.

    Rejects absolute paths and ``..`` traversal that escape the repository's
    test/evidence areas. Returns the resolved, confined path.
    """

    candidate = Path(raw)
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Invalid {label}: {raw!r} ({exc}).") from exc
    for root in ALLOWED_PATH_ROOTS:
        try:
            root_resolved = root.resolve()
        except (OSError, RuntimeError):
            continue
        if resolved == root_resolved or resolved.is_relative_to(root_resolved):
            return resolved
    raise ValueError(
        f"Refusing {label} outside the allowed test/evidence roots: {raw!r}. "
        f"Paths must resolve under one of: {[str(p) for p in ALLOWED_PATH_ROOTS]}."
    )


ADAPTERS = {
    "yaxunit": {
        "framework": "YAxUnit",
        "title": "YAxUnit runner",
        "kind": "command",
        "description": "Local wrapper around scripts/tests/run_yaxunit_tests.py.",
        "default_report": "reports/report.xml",
        "requires": ["1C platform", "configured infobase", "YAxUnit extension"],
    },
    "bsl_manifest": {
        "framework": "BSL",
        "title": "BSL manifest runner",
        "kind": "manifest",
        "description": "Runs tests/bsl/testplan.json through scripts/tests/run_bsl_tests.py.",
        "default_report": None,
        "requires": ["manifest commands configured for the target environment"],
    },
    "vanessa": {
        "framework": "Vanessa",
        "title": "Vanessa runner",
        "kind": "command",
        "description": "Generic Vanessa Automation/ADD command adapter.",
        "default_report": "vanessa-report.xml",
        "requires": ["vanessa-runner or configured command", "1C platform", "test infobase"],
    },
    "1c_tester": {
        "framework": "1C:Tester",
        "title": "1C Tester runner",
        "kind": "command",
        "description": "Generic adapter for 1C:Tester result execution/import.",
        "default_report": "1c-tester-report.xml",
        "requires": ["1C:Tester CLI or exported result file"],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(item, limit=500) for item in values if _clean(item, limit=500)]


def _safe_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {_clean(key, limit=120): _clean(val, limit=1000) for key, val in value.items()}


def _display_command(command: list[str]) -> str:
    return " ".join(command)


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_evidence(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "size": path.stat().st_size if exists else 0,
        "sha256": _sha256(path) if exists else None,
        "kind": "file",
    }


def _audit_path(path: Path | None = None) -> Path:
    if path is not None:
        return path.parent / "audit_log.ndjson"
    return ROOT / "data" / "audit_log.ndjson"


def _audit(action: str, *, target: str, metadata: dict[str, Any], path: Path | None = None) -> None:
    try:
        record_event(
            action=action,
            target=target,
            category="testing",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _output_dir(adapter: str, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    return DEFAULT_OUTPUT_ROOT / adapter


def adapter_catalog() -> dict[str, Any]:
    """Return supported runner adapters and execution constraints."""

    return {
        "adapters": [
            {"id": adapter_id, **definition}
            for adapter_id, definition in sorted(ADAPTERS.items())
        ],
        "defaults": {
            "dry_run": True,
            "execute_requires_allow_external": True,
            "bundle_root": str(DEFAULT_BUNDLE_ROOT),
        },
    }


def build_runner_plan(
    adapter: str,
    *,
    test_files: list[str] | None = None,
    modules: list[str] | None = None,
    selectors: list[str] | None = None,
    manifest_path: str | None = None,
    output_dir: str | None = None,
    report_path: str | None = None,
    cwd: str | None = None,
    env: dict[str, Any] | None = None,
    timeout: int | None = None,
    extra_args: list[str] | None = None,
    change_set_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Build a deterministic runner command plan without executing it."""

    adapter_id = _clean(adapter, limit=80)
    if adapter_id not in ADAPTERS:
        raise ValueError(f"Unsupported test runner adapter: {adapter}")

    definition = ADAPTERS[adapter_id]
    out_dir = _output_dir(adapter_id, output_dir)
    report = Path(report_path) if report_path else None
    default_report = definition.get("default_report")
    if report is None and default_report:
        report = out_dir / str(default_report)

    # The runner process always executes from the repository root. We never honor
    # a caller-supplied cwd: it was an RCE lever (controls relative-path lookups
    # for the spawned binary). The parameter is accepted for plan back-compat but
    # ignored for the actual command.
    safe_cwd = ROOT

    command: list[str]
    caveats: list[str] = []
    if adapter_id == "yaxunit":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "tests" / "run_yaxunit_tests.py"),
            "--output-dir",
            str(out_dir),
            "--report-format",
            "jUnit",
        ]
        if test_files:
            command.extend(["--test-files", *test_files])
        if modules or selectors:
            command.extend(["--modules", *(modules or selectors or [])])
        if dry_run:
            command.append("--dry-run")
        caveats.append("Actual YAxUnit execution requires a configured 1C infobase and platform binary.")
    elif adapter_id == "bsl_manifest":
        manifest = (
            _confine_path(manifest_path, label="manifest_path")
            if manifest_path
            else DEFAULT_BSL_MANIFEST
        )
        command = [
            sys.executable,
            str(ROOT / "scripts" / "tests" / "run_bsl_tests.py"),
            "--manifest",
            str(manifest),
            "--artifacts-dir",
            str(out_dir),
        ]
        caveats.append(
            "Manifest commands run under run_bsl_tests.py, which itself enforces an "
            "executable allow-list; the manifest path is confined to the repo tests/ root."
        )
    elif adapter_id == "vanessa":
        command = ["vanessa-runner", "run", "--workspace", str(safe_cwd), "--report", str(report or out_dir / "vanessa-report.xml")]
        if selectors:
            command.extend(["--filter", ",".join(selectors)])
        caveats.append("Vanessa runs from the repository root with a fixed argv; custom wrappers are not accepted from the request.")
    else:
        command = ["1ctestc", "run", "--out", str(report or out_dir / "1c-tester-report.xml")]
        if selectors:
            command.extend(["--filter", ",".join(selectors)])
        caveats.append("1C:Tester execution is environment-specific; exported result import is preferred by default.")

    # extra_args, env and cwd are deliberately NOT taken from the request body:
    # each was an injection lever (arbitrary trailing argv / process environment /
    # working directory). They are accepted in the signature for back-compat but
    # dropped here. Validate the resolved executable against the allow-list so a
    # bad plan can never reach subprocess.run.
    _assert_executable_allowed(command)
    dropped_inputs = [
        name
        for name, value in (("env", env), ("cwd", cwd), ("extra_args", extra_args))
        if value
    ]

    expected_reports = [str(report)] if report else []
    return {
        "adapter": adapter_id,
        "framework": definition["framework"],
        "title": definition["title"],
        "description": definition["description"],
        "dry_run": bool(dry_run),
        "command": command,
        "command_text": _display_command(command),
        "cwd": str(safe_cwd),
        "env": {},
        "timeout": int(timeout or 1800),
        "change_set_id": _clean(change_set_id, limit=160) or None,
        "expected_reports": expected_reports,
        "output_dir": str(out_dir),
        "requires": definition["requires"],
        "caveats": caveats,
        "dropped_request_inputs": dropped_inputs,
    }


def create_evidence_bundle(
    run_id: str,
    *,
    attachment_paths: list[str],
    copy_files: bool = False,
    bundle_root: Path | None = None,
) -> dict[str, Any]:
    """Create a checksum manifest for evidence files, optionally copying them."""

    root = bundle_root or DEFAULT_BUNDLE_ROOT
    bundle_dir = root / _clean(run_id, limit=160)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for raw in attachment_paths:
        source = Path(raw)
        info = _file_evidence(source)
        if copy_files and info["exists"]:
            target = bundle_dir / source.name
            shutil.copy2(source, target)
            info["bundled_path"] = str(target)
        files.append(info)
    manifest = {
        "run_id": _clean(run_id, limit=160),
        "created_at": _now(),
        "copy_files": bool(copy_files),
        "files": files,
        "summary": {
            "files": len(files),
            "present": sum(1 for item in files if item["exists"]),
            "missing": sum(1 for item in files if not item["exists"]),
        },
    }
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    _audit(
        "test.evidence.bundle",
        target=manifest["run_id"],
        metadata={"summary": manifest["summary"], "manifest_path": str(manifest_path)},
        path=(bundle_root or DEFAULT_BUNDLE_ROOT).parent / "bundle_store",
    )
    return manifest


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251", errors="ignore")


def _allure_results(path: Path) -> list[dict[str, Any]]:
    files = sorted(path.glob("*-result.json")) if path.is_dir() else [path]
    if path.is_dir() and not files:
        files = sorted(path.glob("*.json"))
    results = []
    for item in files:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict):
                    results.append(_json_result(row, source=item))
            continue
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            for row in payload["results"]:
                if isinstance(row, dict):
                    results.append(_json_result(row, source=item))
            continue
        if isinstance(payload, dict):
            results.append(_json_result(payload, source=item))
    return results


def _json_result(payload: dict[str, Any], *, source: Path) -> dict[str, Any]:
    status = str(payload.get("status") or "unknown").lower()
    if status == "broken":
        status = "error"
    duration_ms = payload.get("duration_ms")
    if duration_ms is None and isinstance(payload.get("time"), dict):
        duration_ms = (payload["time"].get("duration") or 0)
    details = payload.get("statusDetails") if isinstance(payload.get("statusDetails"), dict) else {}
    return {
        "id": payload.get("id") or payload.get("uuid") or payload.get("fullName") or payload.get("name"),
        "name": payload.get("name") or payload.get("fullName") or source.stem,
        "framework": payload.get("framework") or "JSON",
        "status": status,
        "duration_ms": duration_ms or 0,
        "message": payload.get("message") or details.get("message") or "",
        "path": str(source),
    }


def import_result_file(
    result_path: str,
    *,
    result_format: str = "auto",
    title: str | None = None,
    framework: str | None = None,
    change_set_id: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Import JUnit XML, generic JSON or Allure result files into test evidence."""

    # Confine the caller-supplied result path to the repo test/evidence roots.
    # Without this, an unauthenticated import could read any file on disk
    # (e.g. credentials) by passing an absolute or traversal path.
    target = _confine_path(result_path, label="result_path")
    if not target.exists():
        raise FileNotFoundError(f"Result path not found: {result_path}")
    fmt = _clean(result_format or "auto", limit=40).lower()
    if fmt == "auto":
        fmt = "allure" if target.is_dir() else ("junit" if target.suffix.lower() == ".xml" else "json")

    if fmt in {"junit", "xml"}:
        run = import_junit_xml(
            xml_text=_read_text(target),
            title=title or target.stem,
            framework=framework or "JUnit",
            change_set_id=change_set_id,
            path=path,
            artifact_path=artifact_path,
        )
        _audit(
            "test.result.import_file",
            target=run["id"],
            metadata={"format": fmt, "path": str(target), "status": run["status"]},
            path=path,
        )
        return run

    results = _allure_results(target)
    if not results:
        raise ValueError(f"No JSON/Allure test results found in {result_path}")
    run = record_test_run(
        title=title or target.stem,
        framework=framework or ("Allure" if fmt == "allure" else "JSON"),
        results=results,
        change_set_id=change_set_id,
        evidence=[_file_evidence(target) if target.is_file() else {"kind": fmt, "path": str(target), "files": len(results)}],
        path=path,
        artifact_path=artifact_path,
    )
    _audit(
        "test.result.import_file",
        target=run["id"],
        metadata={"format": fmt, "path": str(target), "status": run["status"]},
        path=path,
    )
    return run


def run_test_adapter(
    adapter: str,
    *,
    execute: bool = False,
    allow_external: bool = False,
    import_results: bool = True,
    path: Path | None = None,
    artifact_path: Path | None = None,
    bundle_root: Path | None = None,
    **plan_kwargs: Any,
) -> dict[str, Any]:
    """Plan or execute a test adapter and persist evidence."""

    plan = build_runner_plan(adapter, dry_run=not execute, **plan_kwargs)
    if not execute:
        run = record_test_run(
            title=f"Dry-run {plan['title']}",
            framework=plan["framework"],
            change_set_id=plan.get("change_set_id"),
            command=plan["command_text"],
            results=[
                {
                    "id": f"{plan['adapter']}:dry-run",
                    "name": "Runner dry-run plan",
                    "status": "skipped",
                    "message": "External test execution was not requested.",
                }
            ],
            evidence=[{"kind": "runner_plan", "plan": plan}],
            dry_run=True,
            path=path,
            artifact_path=artifact_path,
        )
        _audit(
            "test.runner.plan",
            target=run["id"],
            metadata={"adapter": plan["adapter"], "framework": plan["framework"], "change_set_id": plan.get("change_set_id")},
            path=path,
        )
        return {"executed": False, "plan": plan, "run": run}

    # Kill switch: process execution is refused unless an operator has explicitly
    # opted in on the host. This is checked before any allow_external handling so
    # the default deployment can never spawn a process from an HTTP/MCP request.
    if not _test_execution_enabled():
        raise TestExecutionDisabled(
            "Test execution is disabled. Set "
            f"{TEST_EXECUTION_FLAG}=1 on the host to allow local test-runner spawning."
        )

    if not allow_external:
        raise ValueError("External test execution requires allow_external=True")

    # Defense-in-depth: re-validate the executable at the spawn boundary even
    # though build_runner_plan already checked it.
    _assert_executable_allowed(plan["command"])

    output_dir = Path(plan["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"{plan['adapter']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.log"
    # Use a clean, fixed environment and the repo root as cwd. We never merge a
    # caller-supplied env (plan["env"] is forced empty upstream) so request data
    # cannot influence the spawned process environment.
    env = os.environ.copy()
    started_at = _now()
    try:
        result = subprocess.run(
            plan["command"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=int(plan["timeout"]),
            check=False,
        )
        exit_code = result.returncode
        log_path.write_text((result.stdout or "") + ("\n" + result.stderr if result.stderr else ""), encoding="utf-8")
    except FileNotFoundError as exc:
        exit_code = 127
        log_path.write_text(f"Runner not found: {exc}\n", encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        log_path.write_text(f"Timed out after {exc.timeout} seconds\n{exc.stdout or ''}\n{exc.stderr or ''}", encoding="utf-8")

    attachment_paths = [str(log_path), *[item for item in plan["expected_reports"] if Path(item).exists()]]
    imported = None
    if import_results:
        for report in plan["expected_reports"]:
            report_path = Path(report)
            if report_path.exists():
                imported = import_result_file(
                    str(report_path),
                    title=f"{plan['title']} results",
                    framework=plan["framework"],
                    change_set_id=plan.get("change_set_id"),
                    path=path,
                    artifact_path=artifact_path,
                )
                break

    run = imported or record_test_run(
        title=plan["title"],
        framework=plan["framework"],
        change_set_id=plan.get("change_set_id"),
        command=plan["command_text"],
        results=[
            {
                "id": f"{plan['adapter']}:exit-code",
                "name": "Runner process",
                "status": "passed" if exit_code == 0 else "failed",
                "message": f"External runner exit code: {exit_code}",
            }
        ],
        evidence=[_file_evidence(log_path), {"kind": "runner_plan", "plan": plan}],
        dry_run=False,
        path=path,
        artifact_path=artifact_path,
    )
    bundle = create_evidence_bundle(run["id"], attachment_paths=attachment_paths, bundle_root=bundle_root)
    _audit(
        "test.runner.execute",
        target=run["id"],
        metadata={"adapter": plan["adapter"], "exit_code": exit_code, "status": run["status"]},
        path=path,
    )
    return {
        "executed": True,
        "started_at": started_at,
        "finished_at": _now(),
        "exit_code": exit_code,
        "plan": plan,
        "run": run,
        "bundle": bundle,
    }
