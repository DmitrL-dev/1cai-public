"""Internal owned ibcmd file execution; no preview qualification or live apply.

The coordinator supplies a trusted profile and fixture inputs below project state.
Only ibcmd itself is pinned; runtime dependencies are not yet qualified. All run
artifacts are retained. Recovery reads evidence and never restarts a process.
"""
from dataclasses import asdict
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import threading
import time

from ._windows_source_tree import pinned_directory, pinned_retained, read_retained
from .edt_command import (
    FixtureCommandRequest,
    IBCmdProfile,
    _windows_path,
    plan_fixture_commands,
    validate_fixture_commands,
)
from .edt_execution import write_record
from .edt_inventory import exported_inventory
from .edt_profiles import PERMISSIONS, parse_json
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .native_process import OwnedProcess
from .native_resources import DiskBudget, DiskLimits, project_slot, reserve_run
from .platform_check import _pin_inputs
from .snapshots import validate_operation_id
from .source_paths import validate_inventory_paths

DISK_LIMITS = DiskLimits()
MAX_FILE = 256 * 1024**2
RECOVERY = "EDT_FIXTURE_RECOVERY_REQUIRED"


def _require(value, code, message):
    if not value:
        raise CoreError(code, message)


def _check(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)


def _root(ctx, fixture_root):
    _check(ctx)
    _require(
        os.name == "nt", "EDT_FIXTURE_UNSUPPORTED", "Fixture execution requires Windows"
    )
    root = Path(str(_windows_path(fixture_root)))
    _require(
        root == ctx.state.path.parent.absolute()
        and not root.is_relative_to(ctx.source_root.absolute()),
        "EDT_FIXTURE_INVALID",
        "Fixture root must be project state outside live source",
    )
    return root


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _inputs(root, value):
    inputs = Path(str(_windows_path(value)))
    _require(
        inputs.is_relative_to(root / "fixture-inputs")
        and inputs != root / "fixture-inputs",
        "EDT_FIXTURE_INVALID",
        "Fixture inputs must be an owned input copy",
    )
    return inputs


def _read(path, key):
    try:
        value = parse_json(read_retained(path, 2 * 1024**2))
        _require(
            type(value) is dict and key in value, RECOVERY, "Invalid fixture record"
        )
        _require(
            _seal({k: v for k, v in value.items() if k != key}, key) == value,
            RECOVERY,
            "Fixture record hash differs",
        )
        return value
    except (OSError, ValueError, TypeError, CoreError) as exc:
        raise CoreError(
            RECOVERY, "Fixture record is absent, incomplete or changed"
        ) from exc


def _intent(ctx, plan, profile, request, root, input_root, rows):
    return _seal(
        {
            "schema": 1,
            "project_id": ctx.project_id,
            "operation_id": request.operation_id,
            "profile_id": sha256(canonical_bytes(asdict(profile))),
            "fixture_root": str(root),
            "input_root": str(input_root),
            "profile": asdict(profile),
            "request": asdict(request),
            "plan": {
                **asdict(plan),
                "commands": [_command_record(command) for command in plan.commands],
            },
            "input_inventory": rows,
        },
        "request_id",
    )


def _command_record(command):
    return {**asdict(command), "argv": list(command.argv)}


class _Capture:
    """Drain inherited pipes, retaining at most one shared stdout/stderr budget."""

    def __init__(self, run, prefix, maximum):
        self.maximum, self.saved = maximum, 0
        self.lock, self.overflow = threading.Lock(), threading.Event()
        self.error, self.threads, self.writers = None, [], []
        try:
            for label in ("stdout", "stderr"):
                path = run / f"{prefix}-{label}.log"
                output = path.open("xb")
                try:
                    reader_fd, writer_fd = os.pipe()
                except BaseException:
                    output.close()
                    raise
                reader = os.fdopen(reader_fd, "rb", buffering=0)
                writer = os.fdopen(writer_fd, "wb", buffering=0)
                self.writers.append(writer)
                thread = threading.Thread(
                    target=self._drain, args=(label, reader, output), daemon=True
                )
                self.threads.append(thread)
                thread.start()
        except BaseException:
            self.finish()
            raise

    def _drain(self, label, reader, output):
        try:
            with reader, output:
                while raw := reader.read(64 * 1024):
                    with self.lock:
                        kept = raw[: max(0, self.maximum - self.saved)]
                        output.write(kept)
                        self.saved += len(kept)
                        if len(kept) != len(raw):
                            self.overflow.set()
                output.flush()
                os.fsync(output.fileno())
        except BaseException as exc:
            self.error = type(exc).__name__

    def close_writers(self):
        for writer in self.writers:
            writer.close()

    def finish(self):
        self.close_writers()
        deadline = time.monotonic() + 5
        for thread in self.threads:
            thread.join(max(0, deadline - time.monotonic()))
        _require(
            not any(thread.is_alive() for thread in self.threads),
            "EDT_FIXTURE_CAPTURE_TIMEOUT",
            "Owned output streams did not close",
        )
        _require(
            self.error is None,
            "EDT_FIXTURE_CAPTURE_FAILED",
            "Owned output could not be retained",
        )

    def check(self):
        _require(
            not self.overflow.is_set(),
            "EDT_FIXTURE_OUTPUT_LIMIT",
            "Fixture output exceeds 2 MiB",
        )
        _require(
            self.error is None,
            "EDT_FIXTURE_CAPTURE_FAILED",
            "Owned output could not be retained",
        )


def _file_row(path, maximum=MAX_FILE):
    with pinned_retained(path, maximum) as raw:
        return {"size": len(raw), "sha256": sha256(raw)}


def _step_request(intent, command, index):
    return _seal(
        {
            "schema": 1,
            "request_id": intent["request_id"],
            "index": index,
            "command": _command_record(command),
        },
        "command_id",
    )


def _run_command(run, intent, command, index, job, check):
    prefix = f"{index:03d}"
    request = _step_request(intent, command, index)
    check()
    write_record(run / f"{prefix}-request.json", request)
    child, capture, error, exit_code = None, None, None, None
    closed, attempted = False, False
    deadline = time.monotonic() + command.timeout_seconds
    try:
        capture = _Capture(run, prefix, command.max_output_bytes)
        check()
        attempted = True
        child = OwnedProcess(
            subprocess.list2cmdline(command.argv),
            command.argv[0],
            *capture.writers,
            parent_job=job,
            cwd=command.cwd,
        )
        capture.close_writers()
        while True:
            check()
            capture.check()
            _require(
                time.monotonic() < deadline,
                "EDT_FIXTURE_TIMEOUT",
                "Fixture command deadline expired",
            )
            exit_code = child.poll()
            if exit_code is not None:
                break
            time.sleep(0.025)
    except BaseException as exc:
        error = exc
    finally:
        try:
            if child is not None:
                child.close()
            closed = not job.active()
            _require(
                closed, "NATIVE_CLEANUP_TIMEOUT", "Fixture descendants remain active"
            )
        except BaseException as exc:
            error = error or exc
        try:
            if capture is not None:
                capture.finish()
                capture.check()
        except BaseException as exc:
            error = error or exc
    if error is None and time.monotonic() >= deadline:
        error = CoreError(
            "EDT_FIXTURE_TIMEOUT", "Fixture completion arrived after deadline"
        )
    if error is None and exit_code != 0:
        error = CoreError(
            "EDT_FIXTURE_COMMAND_FAILED", "Fixture command returned a nonzero exit code"
        )
    reason = (
        error.code
        if isinstance(error, CoreError)
        else type(error).__name__
        if error
        else None
    )
    status = (
        "completed"
        if error is None
        else (
            "failed"
            if not attempted or reason == "EDT_FIXTURE_COMMAND_FAILED"
            else "OUTCOME_UNKNOWN"
        )
    )
    outcome = _seal(
        {
            "schema": 1,
            "request_id": intent["request_id"],
            "command_id": request["command_id"],
            "index": index,
            "status": status,
            "reason": reason,
            "exit_code": exit_code,
            "process_tree_closed": closed,
            "process_attempted": attempted,
            "logs": {
                label: _file_row(run / f"{prefix}-{label}.log")
                for label in ("stdout", "stderr")
                if (run / f"{prefix}-{label}.log").exists()
            },
        },
        "outcome_id",
    )
    write_record(run / f"{prefix}-outcome.json", outcome)
    if error is not None:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise error
        raise CoreError(
            reason, "Fixture execution stopped; inspect retained evidence"
        ) from error
    return outcome


def _validated_outcome(run, intent, command, index):
    saved_request = _read(run / f"{index:03d}-request.json", "command_id")
    saved = _read(run / f"{index:03d}-outcome.json", "outcome_id")
    _require(
        canonical_bytes(saved_request)
        == canonical_bytes(_step_request(intent, command, index)),
        RECOVERY,
        "Fixture step request differs",
    )
    try:
        status, reason, exit_code = saved["status"], saved["reason"], saved["exit_code"]
        _require(
            type(status) is str
            and status in {"completed", "failed", "OUTCOME_UNKNOWN"}
            and (reason is None or type(reason) is str and 1 <= len(reason) <= 128)
            and (
                exit_code is None
                or type(exit_code) is int
                and 0 <= exit_code <= 0xFFFFFFFF
            )
            and type(saved["process_tree_closed"]) is bool
            and type(saved["process_attempted"]) is bool
            and type(saved["logs"]) is dict
            and set(saved["logs"]) <= {"stdout", "stderr"},
            RECOVERY,
            "Invalid fixture step outcome",
        )
        expected = _seal(
            {
                "schema": 1,
                "request_id": intent["request_id"],
                "command_id": saved_request["command_id"],
                "index": index,
                "status": status,
                "reason": reason,
                "exit_code": exit_code,
                "process_tree_closed": saved["process_tree_closed"],
                "process_attempted": saved["process_attempted"],
                "logs": saved["logs"],
            },
            "outcome_id",
        )
        _require(
            canonical_bytes(saved) == canonical_bytes(expected),
            RECOVERY,
            "Fixture step binding differs",
        )
        if status == "completed":
            _require(
                exit_code == 0
                and reason is None
                and saved["process_tree_closed"]
                and saved["process_attempted"]
                and set(saved["logs"]) == {"stdout", "stderr"},
                RECOVERY,
                "Incomplete fixture step",
            )
        if status == "failed" and saved["process_attempted"]:
            _require(
                reason == "EDT_FIXTURE_COMMAND_FAILED"
                and type(exit_code) is int
                and exit_code != 0
                and saved["process_tree_closed"],
                RECOVERY,
                "Only a confirmed nonzero exit is a known command failure",
            )
        for label, row in saved["logs"].items():
            _require(
                row
                == _file_row(
                    run / f"{index:03d}-{label}.log", command.max_output_bytes
                ),
                RECOVERY,
                "Fixture retained log differs",
            )
        _require(
            sum(row["size"] for row in saved["logs"].values())
            <= command.max_output_bytes,
            RECOVERY,
            "Fixture retained logs exceed the command budget",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CoreError(RECOVERY, "Fixture step schema differs") from exc
    return saved


def _terminal(
    intent, status, *, reason=None, steps=(), artifacts=None, cleanup="unconfirmed"
):
    return _seal(
        {
            "schema": 1,
            "project_id": intent["project_id"],
            "operation_id": intent["operation_id"],
            "profile_id": intent["profile_id"],
            "request_id": intent["request_id"],
            "status": status,
            "reason": reason,
            "step_ids": list(steps),
            "artifacts": artifacts,
            "cleanup": {"process_tree": cleanup, "artifacts": "retained"},
            "metadata_verified": False,
            "live_apply_allowed": False,
            "live_source_written": False,
        },
        "result_id",
    )


def execute_fixture_commands(ctx, plan, profile, request, *, fixture_root, input_root):
    """Run one new fixture operation. Existing UUIDs always require readback.

    This is an internal coordinator API: profile and input locator are trusted
    inputs, not CLI/MCP fields. Input copies must be below state/fixture-inputs.
    """
    root = _root(ctx, fixture_root)
    plan = validate_fixture_commands(plan, profile, request, fixture_root=str(root))
    inputs = _inputs(root, input_root)
    run = Path(plan.commands[0].cwd)
    _require(
        not os.path.lexists(run),
        "EDT_FIXTURE_CONFLICT",
        "Fixture operation already exists; do not replay",
    )
    intent, steps, attempted = None, [], False
    with pinned_directory(root), pinned_retained(
        Path(profile.executable), MAX_FILE
    ) as binary:
        _require(
            sha256(binary) == profile.sha256,
            "EDT_FIXTURE_PROFILE_CHANGED",
            "ibcmd binary hash differs",
        )
        rows = exported_inventory(inputs, authorize=lambda: _check(ctx))
        _require(
            bool(rows) and sha256(canonical_bytes(rows)) == request.input_digest,
            "EDT_FIXTURE_INPUT_CHANGED",
            "Fixture input inventory differs",
        )
        with _pin_inputs(inputs, rows):
            _require(
                exported_inventory(inputs, authorize=lambda: _check(ctx)) == rows,
                "EDT_FIXTURE_INPUT_CHANGED",
                "Fixture input tree changed before admission",
            )
            try:
                with project_slot(root) as job:
                    parent = run.parent
                    parent.mkdir(exist_ok=True)
                    with pinned_directory(parent):
                        _check(ctx)
                        try:
                            admission = reserve_run(root, run, limits=DISK_LIMITS)
                        except FileExistsError as exc:
                            raise CoreError(
                                "EDT_FIXTURE_CONFLICT",
                                "Fixture operation already exists",
                            ) from exc
                        with pinned_directory(run):
                            intent = _intent(
                                ctx, plan, profile, request, root, inputs, rows
                            )
                            write_record(run / "request.json", intent)
                            write_record(run / "admission.json", admission)
                            budget = DiskBudget(root, run, DISK_LIMITS)

                            def check():
                                _check(ctx)
                                budget.check()

                            target = run / "input"
                            target.mkdir()
                            for row in rows:
                                check()
                                path = target / row["path"]
                                path.parent.mkdir(parents=True, exist_ok=True)
                                raw = read_retained(inputs / row["path"], MAX_FILE)
                                _require(
                                    len(raw) == row["size"]
                                    and sha256(raw) == row["sha256"],
                                    "EDT_FIXTURE_INPUT_CHANGED",
                                    "Fixture input bytes changed",
                                )
                                with path.open("xb") as output:
                                    output.write(raw)
                                    output.flush()
                                    os.fsync(output.fileno())
                            with _pin_inputs(target, rows), ExitStack() as output_pins:
                                for index, command in enumerate(plan.commands, 1):
                                    check()
                                    attempted = True
                                    outcome = _run_command(
                                        run, intent, command, index, job, check
                                    )
                                    steps.append(outcome["outcome_id"])
                                    if index == 1:
                                        _file_row(run / "infobase" / "1Cv8.1CD")
                                        output_pins.enter_context(
                                            pinned_directory(run / "infobase")
                                        )
                                    elif index == 2:
                                        output_pins.enter_context(
                                            pinned_retained(
                                                run / "candidate.cf", MAX_FILE
                                            )
                                        )
                                check()
                                candidate = _file_row(run / "candidate.cf")
                                restored = exported_inventory(
                                    run / "roundtrip", authorize=check
                                )
                                _require(
                                    candidate["size"] > 0 and bool(restored),
                                    "EDT_FIXTURE_OUTPUT_INVALID",
                                    "Fixture output is empty",
                                )
                                artifacts = {
                                    "candidate": candidate,
                                    "roundtrip_inventory": restored,
                                }
                                budget.check(force=True)
                                _require(
                                    exported_inventory(target, authorize=check) == rows,
                                    "EDT_FIXTURE_INPUT_CHANGED",
                                    "Materialized fixture input changed",
                                )
                _check(ctx)
            except BaseException as exc:
                if intent is not None and not (run / "report.json").exists():
                    reason = (
                        exc.code if isinstance(exc, CoreError) else type(exc).__name__
                    )
                    status = (
                        "OUTCOME_UNKNOWN"
                        if attempted and reason != "EDT_FIXTURE_COMMAND_FAILED"
                        else "failed"
                    )
                    for index in range(len(steps) + 1, 4):
                        path = run / f"{index:03d}-outcome.json"
                        if not path.exists():
                            break
                        try:
                            saved = _read(path, "outcome_id")
                            steps.append(saved["outcome_id"])
                        except CoreError:
                            status = "OUTCOME_UNKNOWN"
                            break
                    failure = _terminal(intent, status, reason=reason, steps=steps)
                    with pinned_directory(run):
                        write_record(run / "failure.json", failure)
                raise
    # A failed pin/job teardown must not leave a completed terminal receipt.
    _check(ctx)
    result = _terminal(
        intent, "completed", steps=steps, artifacts=artifacts, cleanup="closed"
    )
    with pinned_directory(run):
        write_record(run / "report.json", result)
    return result


def get_fixture_result(ctx, operation_id, *, fixture_root):
    """Read validated evidence. Missing terminal evidence is never replay authority."""
    root = _root(ctx, fixture_root)
    run = root / "ibcmd-fixtures" / validate_operation_id(operation_id)
    with pinned_directory(run):
        intent = _read(run / "request.json", "request_id")
        try:
            profile = IBCmdProfile(**intent["profile"])
            request = FixtureCommandRequest(**intent["request"])
            plan = plan_fixture_commands(profile, request, fixture_root=str(root))
            inputs = _inputs(root, intent["input_root"])
            rows = intent["input_inventory"]
            _require(
                type(rows) is list and 1 <= len(rows) <= 8192,
                RECOVERY,
                "Invalid fixture inventory",
            )
            for row in rows:
                _require(
                    type(row) is dict
                    and set(row) == {"path", "size", "sha256"}
                    and type(row["path"]) is str
                    and type(row["size"]) is int
                    and 0 <= row["size"] <= MAX_FILE
                    and type(row["sha256"]) is str
                    and len(row["sha256"]) == 64
                    and all(c in "0123456789abcdef" for c in row["sha256"]),
                    RECOVERY,
                    "Invalid fixture inventory row",
                )
            validate_inventory_paths(row["path"] for row in rows)
            _require(
                rows == sorted(rows, key=lambda row: row["path"]),
                RECOVERY,
                "Unsorted fixture inventory",
            )
            expected = _intent(ctx, plan, profile, request, root, inputs, rows)
            _require(
                canonical_bytes(intent) == canonical_bytes(expected)
                and request.operation_id == operation_id
                and request.input_digest
                == sha256(canonical_bytes(intent["input_inventory"])),
                RECOVERY,
                "Fixture request binding differs",
            )
        except (KeyError, TypeError, ValueError, CoreError) as exc:
            raise CoreError(RECOVERY, "Fixture request schema differs") from exc
        reports = [p for p in (run / "report.json", run / "failure.json") if p.exists()]
        _require(len(reports) <= 1, RECOVERY, "Fixture has competing terminal records")
        if not reports:
            return _terminal(intent, "OUTCOME_UNKNOWN", reason="incomplete_operation")
        result = _read(reports[0], "result_id")
        try:
            _require(
                result["status"] in {"completed", "failed", "OUTCOME_UNKNOWN"}
                and result["cleanup"]["process_tree"]
                in {"closed", "unconfirmed", "not_started"}
                and type(result["step_ids"]) is list
                and len(result["step_ids"]) <= 3
                and (
                    result["reason"] is None
                    or type(result["reason"]) is str
                    and 1 <= len(result["reason"]) <= 128
                )
                and result
                == _terminal(
                    intent,
                    result["status"],
                    reason=result["reason"],
                    steps=result["step_ids"],
                    artifacts=result["artifacts"],
                    cleanup=result["cleanup"]["process_tree"],
                ),
                RECOVERY,
                "Fixture result binding or schema differs",
            )
            outcomes = []
            for index, step_id in enumerate(result["step_ids"], 1):
                saved = _validated_outcome(run, intent, plan.commands[index - 1], index)
                _require(
                    saved["outcome_id"] == step_id,
                    RECOVERY,
                    "Fixture result references another step",
                )
                outcomes.append(saved)
            if result["status"] != "completed":
                _require(
                    reports[0].name == "failure.json"
                    and result["artifacts"] is None
                    and result["reason"] is not None,
                    RECOVERY,
                    "Invalid fixture failure receipt",
                )
                if result["status"] == "failed" and (run / "001-request.json").exists():
                    _require(
                        bool(outcomes)
                        and outcomes[-1]["status"] == "failed"
                        and outcomes[-1]["reason"] == result["reason"],
                        RECOVERY,
                        "Unknown fixture execution cannot be reported as failed",
                    )
            if result["status"] == "completed":
                _require(
                    reports[0].name == "report.json"
                    and result["reason"] is None
                    and result["cleanup"]["process_tree"] == "closed"
                    and len(result["step_ids"]) == 3,
                    RECOVERY,
                    "Fixture completion is incomplete",
                )
                for saved in outcomes:
                    _require(
                        saved["status"] == "completed",
                        RECOVERY,
                        "Fixture command receipt differs",
                    )
                _require(
                    result["artifacts"]
                    == {
                        "candidate": _file_row(run / "candidate.cf"),
                        "roundtrip_inventory": exported_inventory(
                            run / "roundtrip", authorize=lambda: _check(ctx)
                        ),
                    },
                    RECOVERY,
                    "Fixture output differs from its receipt",
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise CoreError(RECOVERY, "Fixture result schema differs") from exc
        _check(ctx)
        return result
