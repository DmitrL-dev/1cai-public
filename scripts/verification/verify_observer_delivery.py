"""Exercise the installed observer across processes with owned artificial sources."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def verify(python, scanner, output):
    python, scanner = python.resolve(strict=True), scanner.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    module = source / "CommonModules/Demo/Ext/Module.bsl"
    module.parent.mkdir(parents=True)
    original = b"Function Value() Export\nReturn 1;\nEndFunction\n"
    module.write_bytes(original)
    registry = output / "registry.sqlite3"
    profile = output / "observer"

    def call(module_name, *args, code=0):
        completed = subprocess.run(
            [str(python), "-I", "-m", module_name, *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        assert completed.returncode == code, (
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
        return json.loads(completed.stdout)

    call("rentgen_core", "registry-init", "--registry", registry)
    project = call(
        "rentgen_core",
        "project-register",
        "--registry",
        registry,
        "--source-root",
        source,
        "--state-root",
        output / "state",
        "--name",
        "Observer acceptance",
    )["result"]["project_id"]
    common = ("--registry", registry, "--project", project, "--profile", profile)
    call("rentgen_core.observer_cli", "init", *common)
    first = call(
        "rentgen_core.observer_cli",
        "run",
        *common,
        "--scanner",
        scanner,
        "--cycles",
        "1",
    )["result"]
    assert first["status"] == "reported"
    generations = sorted(p.name for p in (output / "state/generations").iterdir())
    log = output / "worker.jsonl"
    worker = None
    with log.open("wb") as stream:
        try:
            worker = subprocess.Popen(
                [
                    str(python),
                    "-I",
                    "-m",
                    "rentgen_core.observer_cli",
                    "run",
                    *map(str, common),
                    "--scanner",
                    str(scanner),
                    "--interval",
                    "60",
                ],
                stdout=stream,
                stderr=subprocess.PIPE,
            )
            deadline = time.monotonic() + 15
            while (
                log.stat().st_size == 0
                and worker.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)
            assert (
                log.stat().st_size > 0 and worker.poll() is None
            ), "Worker never reached its first result"
            event = json.loads(log.read_text("utf-8"))
            assert event["result"]["status"] == "unchanged"
            rival = call(
                "rentgen_core.observer_cli",
                "run",
                *common,
                "--scanner",
                scanner,
                "--cycles",
                "1",
                code=2,
            )
            assert rival["error"]["code"] == "OBSERVER_BUSY"
        finally:
            if worker is not None:
                if worker.poll() is None:
                    worker.terminate()
                worker.communicate(timeout=15)
    assert (
        sorted(p.name for p in (output / "state/generations").iterdir()) == generations
    )
    module.write_bytes(original.replace(b"1", b"2"))
    second = call(
        "rentgen_core.observer_cli",
        "run",
        *common,
        "--scanner",
        scanner,
        "--cycles",
        "1",
    )["result"]
    assert (
        second["status"] == "reported" and second["snapshot_id"] != first["snapshot_id"]
    )
    status = call("rentgen_core.observer_cli", "status", *common, "--limit", "10")[
        "result"
    ]
    assert len(status["jobs"]) == len(status["reports"]) == 2
    latest = status["reports"][0]
    assert latest["before"] == first["snapshot_id"]
    assert latest["after"] == second["snapshot_id"]
    assert latest["changes"]["counts"] == {
        "added": 0,
        "removed": 0,
        "modified": 1,
        "unchanged": 0,
    }
    assert latest["quality"]["status"] == "not_run"
    assert module.read_bytes() == original.replace(b"1", b"2")
    report = {
        "accepted": True,
        "separate_processes": True,
        "cross_process_lock": True,
        "recovery_after_idle_process_termination": True,
        "unchanged_source_no_generation": True,
        "persisted_reports": 2,
        "modified_files": 1,
        "source_bytes_preserved": True,
        "model_calls": 0,
        "scope": "Installed file-change observer, not quality/business metrics or 1C execution",
    }
    (output / "acceptance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--scanner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.python, args.scanner, args.output)))
