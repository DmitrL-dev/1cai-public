"""Foreground local observer; a service manager may own the process externally."""
import json
from pathlib import Path
import sys
import time

from .cli import _Parser, _Once, _fields, _json_file
from .errors import CoreError
from .git_observer import Finding, FindingReport, GitObservation
from .local import LocalRuntime
from .local_identity import current_windows_principal
from .observer import Observer


def _parser():
    parser = _Parser(prog="rentgen-observer", description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "action",
        choices=(
            "init",
            "run",
            "status",
            "retry",
            "record-findings",
            "findings-status",
        ),
    )
    for name in ("registry", "profile"):
        parser.add_argument("--" + name, type=Path, required=True, action=_Once)
    parser.add_argument("--project", required=True, action=_Once)
    parser.add_argument("--scanner", type=Path, action=_Once)
    parser.add_argument("--interval", type=int, default=60, action=_Once)
    parser.add_argument("--cycles", type=int, action=_Once)
    parser.add_argument("--limit", type=int, default=1, action=_Once)
    parser.add_argument("--report", type=Path, action=_Once)
    return parser


def _finding_report(path):
    data = _fields(
        _json_file(path),
        ("observation", "profile_id", "scope_id", "complete", "findings"),
    )
    observation = _fields(data["observation"], ("repository", "commit", "ref"))
    if not isinstance(data["findings"], list):
        raise CoreError("INVALID_ARGUMENT", "findings must be a JSON array")
    findings = tuple(
        Finding(**_fields(item, ("rule", "path", "anchor", "message", "line")))
        for item in data["findings"]
    )
    try:
        # Escaped lone surrogates are legal to json.loads but cannot be stored as UTF-8.
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CoreError("INVALID_ARGUMENT", "Expected a UTF-8 JSON report") from exc
    return FindingReport(
        GitObservation(**observation),
        data["profile_id"],
        data["scope_id"],
        data["complete"],
        findings,
    )


def _emit(observer, result, *, findings=False):
    encoded = json.dumps({"result": result}, ensure_ascii=True, allow_nan=False)
    if len(encoded.encode("utf-8")) > 2 * 1024 * 1024:
        raise CoreError(
            "OBSERVER_RESPONSE_LIMIT", "Response exceeds 2 MiB; reduce --limit"
        )
    observer._validate(observer._context(write=findings))
    print(encoded, flush=True)


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        if not 5 <= args.interval <= 86400 or (
            args.cycles is not None and not 1 <= args.cycles <= 10000
        ):
            raise CoreError(
                "INVALID_ARGUMENT", "Interval must be 5..86400; cycles must be 1..10000"
            )
        if args.action == "run" and args.scanner is None:
            raise CoreError("INVALID_ARGUMENT", "run requires --scanner")
        if (args.action == "record-findings") != (args.report is not None):
            raise CoreError(
                "INVALID_ARGUMENT", "--report is required only for record-findings"
            )
        from rentgen_graph.snapshot_adapter import (
            RentgenCapturedGoBuilder,
            RentgenGraphReaderFactory,
        )

        runtime = LocalRuntime(
            args.registry.resolve(),
            RentgenGraphReaderFactory(),
            RentgenCapturedGoBuilder(args.scanner.resolve()) if args.scanner else None,
        )
        observer = Observer(
            runtime, current_windows_principal(), args.project, args.profile
        )
        if args.action == "init":
            observer.initialize()
            _emit(observer, {"status": "initialized"})
        elif args.action == "status":
            _emit(observer, observer.status(limit=args.limit))
        elif args.action == "retry":
            observer.retry()
            _emit(observer, {"status": "retry_enabled"})
        elif args.action == "record-findings":
            observer._validate(observer._context(write=True))
            _emit(
                observer,
                observer.record_findings(_finding_report(args.report)),
                findings=True,
            )
        elif args.action == "findings-status":
            _emit(observer, observer.findings_status(limit=args.limit), findings=True)
        else:
            previous = None
            last_error = False
            with observer.locked():
                cycle = 0
                while args.cycles is None or cycle < args.cycles:
                    try:
                        event = observer._tick()
                        last_error = False
                    except CoreError as exc:
                        if exc.code in {
                            "PROJECT_FORBIDDEN",
                            "PROJECT_NOT_FOUND",
                            "OBSERVER_JOB_FAILED",
                            "OBSERVER_PROFILE_MISMATCH",
                            "OBSERVER_JOURNAL_FULL",
                            "STATE_UNAVAILABLE",
                            "CAPTURE_PLATFORM_UNSUPPORTED",
                        }:
                            raise
                        event = {"status": "error", "code": exc.code}
                        last_error = True
                    if event != previous:
                        _emit(observer, event)
                        previous = event
                    cycle += 1
                    if args.cycles is None or cycle < args.cycles:
                        time.sleep(args.interval)
            return 2 if last_error else 0
        return 0
    except KeyboardInterrupt:
        return 130
    except CoreError as exc:
        print(
            json.dumps({"error": {"code": exc.code, "message": str(exc)}}), flush=True
        )
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "error": {
                        "code": "OBSERVER_STATE_UNAVAILABLE",
                        "message": "Observer state or local IO is unavailable",
                    }
                }
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
