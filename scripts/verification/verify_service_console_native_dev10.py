"""Prove the installed Core dev10 Source Observer console in separate processes."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import rentgen_core as api
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import current_windows_principal
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.observer import Observer
from rentgen_core.source_probe import probe_sources
from rentgen_graph.snapshot_adapter import (
    RentgenCapturedGoBuilder,
    RentgenGraphReaderFactory,
)

from verify_metadata_live_native import check_release, digest, require


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = "CommonModules/ServiceProbe/Ext/Module.bsl"
MODULE_BYTES = (
    "Функция Значение() Экспорт\r\n\tВозврат 1;\r\nКонецФункции\r\n"
).encode("utf-8")
if not __debug__:
    raise RuntimeError("Verification requires assertions; do not use Python -O")


def fixed_local_output(path):
    require(
        os.name == "nt" and path.drive and not str(path).startswith("\\\\"),
        "A fixed local Windows output is required",
    )
    drive_type = ctypes.windll.kernel32.GetDriveTypeW(path.anchor)
    require(drive_type == 3, "Output must be on a fixed local volume")
    require(
        not path.is_relative_to(ROOT), "Output cannot be inside the source checkout"
    )


def run_console(interpreter, config, output, name):
    result = subprocess.run(
        [
            str(interpreter),
            "-I",
            "-m",
            "rentgen_core.service_entry",
            "--console",
            "--config",
            str(config),
        ],
        cwd=output,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    (output / f"{name}.stdout").write_text(result.stdout, encoding="utf-8")
    (output / f"{name}.stderr").write_text(result.stderr, encoding="utf-8")
    return {
        "exit_code": result.returncode,
        "stdout_sha256": sha256(result.stdout.encode("utf-8")),
        "stderr_sha256": sha256(result.stderr.encode("utf-8")),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def public_process(record, *, expected_status):
    if expected_status == "stopped":
        require(
            record["exit_code"] == 0
            and record["stderr"].splitlines()
            in (
                [],
                [
                    "[stage] reading source identity and declarations ...",
                    "[bind] retaining calls and resolving bounded static targets ...",
                ],
            ),
            "Installed console run did not stop cleanly",
        )
        require(
            json.loads(record["stdout"]) == {"status": "stopped", "cycles": 1},
            "Installed console did not complete exactly one cycle",
        )
    else:
        require(
            record["exit_code"] == 2 and not record["stdout"],
            "Wrong-project console run did not fail closed",
        )
        require(
            json.loads(record["stderr"])
            == {"error": {"code": "SERVICE_WORKER_FAILED"}},
            "Wrong-project console error is not bounded",
        )
    return {
        "exit_code": record["exit_code"],
        "stdout_sha256": record["stdout_sha256"],
        "stderr_sha256": record["stderr_sha256"],
        "outcome": expected_status,
    }


def generation_names(state_root):
    folder = state_root / "generations"
    return (
        sorted(path.name for path in folder.iterdir() if path.is_dir())
        if folder.is_dir()
        else []
    )


def verify(args):
    archive = args.release_zip.resolve(strict=True)
    original_scanner = args.scanner.resolve(strict=True)
    release = check_release(archive, args.release_sha256, original_scanner)
    interpreter = Path(sys.executable).resolve(strict=True)
    output = args.output.resolve()
    fixed_local_output(output)
    require(not output.exists(), "Output must be new")
    output.mkdir(parents=True, exist_ok=False)

    source = output / "source"
    module = source / MODULE_PATH
    module.parent.mkdir(parents=True)
    module.write_bytes(MODULE_BYTES)
    scanner = output / "bsl-scan.exe"
    shutil.copyfile(original_scanner, scanner)
    require(
        digest(scanner) == release["scanner_sha256"],
        "Local scanner copy differs from public release",
    )
    principal = current_windows_principal()
    registry = api.ProjectRegistry.create(output / "registry.sqlite3")
    registered = registry.register(
        principal,
        source_root=source,
        state_root=output / "state",
        display_name="Installed service console proof",
    )
    runtime = LocalRuntime(
        registry.path,
        RentgenGraphReaderFactory(),
        RentgenCapturedGoBuilder(scanner),
    )
    observer = Observer(
        runtime, principal, registered.project_id, output / "observer-profile"
    )
    observer.initialize()
    config = {
        "schema": 1,
        "service_name": "Rentgen.ServiceProbe",
        "registry": str(registry.path),
        "profile": str(observer.profile),
        "project": registered.project_id,
        "scanner": str(scanner),
        "interval_seconds": 5,
        "max_cycles": 1,
    }
    config_path = output / "service.json"
    config_path.write_bytes(canonical_bytes(config))
    (output / "local-inputs.json").write_bytes(
        canonical_bytes(
            {
                "release_zip": str(archive),
                "installed_core": str(Path(api.__file__).resolve()),
                "interpreter": str(interpreter),
                "scanner": str(original_scanner),
                "output": str(output),
            }
        )
    )
    source_before = digest(module)
    require(source_before == sha256(MODULE_BYTES), "Owned module differs")
    require(
        not observer.status()["reports"] and not generation_names(output / "state"),
        "New Observer profile is not empty",
    )

    first = run_console(interpreter, config_path, output, "first")
    first_public = public_process(first, expected_status="stopped")
    with observer.locked():
        pass
    first_status = observer.status()
    first_generations = generation_names(output / "state")
    require(
        len(first_status["reports"]) == len(first_status["jobs"]) == 1
        and len(first_generations) == 1,
        "First process did not publish once",
    )
    report = first_status["reports"][0]
    snapshot_id = first_status["last_snapshot"]
    require(
        report["project_id"] == registered.project_id
        and report["after"] == snapshot_id
        and report["changes"]
        == {"kind": "baseline", "files_present": 1, "bytes_present": len(MODULE_BYTES)}
        and report["model_calls"] == 0
        and report["quality"]["status"] == "not_run"
        and report["business_metrics"]["status"] == "not_available"
        and report["source_temporal_atomicity"] == "not_proven",
        "First report differs from bounded Source Observer claim",
    )
    ctx = runtime.resolve(principal, registered.project_id, snapshot_id)
    with ctx.state.transaction(principal) as tx:
        catalog = tx.get_snapshot(snapshot_id)
    source_digest = probe_sources(ctx)[1]
    require(
        catalog.source_digest == source_digest and digest(module) == source_before,
        "Published source digest or live module differs",
    )

    second = run_console(interpreter, config_path, output, "second")
    second_public = public_process(second, expected_status="stopped")
    with observer.locked():
        pass
    second_status = observer.status()
    require(
        second_status["reports"] == first_status["reports"]
        and second_status["jobs"] == first_status["jobs"]
        and second_status["last_snapshot"] == snapshot_id
        and generation_names(output / "state") == first_generations
        and digest(module) == source_before,
        "Restart created new evidence or changed source",
    )

    wrong = dict(config, project=str(uuid4()))
    wrong_path = output / "wrong-project.json"
    wrong_path.write_bytes(canonical_bytes(wrong))
    negative = run_console(interpreter, wrong_path, output, "wrong-project")
    negative_public = public_process(negative, expected_status="rejected")
    with observer.locked():
        pass
    final_status = observer.status()
    require(
        final_status["reports"] == first_status["reports"]
        and final_status["jobs"] == first_status["jobs"]
        and generation_names(output / "state") == first_generations
        and digest(module) == source_before,
        "Wrong-project process changed owned evidence",
    )

    receipt = {
        "schema": 1,
        "source": "installed public Core dev10 Source Observer console on owned BSL fixture",
        "release": release,
        "interpreter_sha256": digest(interpreter),
        "project_id": registered.project_id,
        "snapshot_id": snapshot_id,
        "module": {
            "path": MODULE_PATH,
            "size": len(MODULE_BYTES),
            "sha256": source_before,
        },
        "source_digest": source_digest,
        "report": {
            "operation_id": report["operation_id"],
            "changes": report["changes"],
            "model_calls": report["model_calls"],
            "quality_status": report["quality"]["status"],
            "business_status": report["business_metrics"]["status"],
            "source_temporal_atomicity": report["source_temporal_atomicity"],
        },
        "processes": {
            "first": first_public,
            "second": second_public,
            "wrong_project": negative_public,
        },
        "reports_after_first": len(first_status["reports"]),
        "reports_after_restart": len(second_status["reports"]),
        "reports_after_rejection": len(final_status["reports"]),
        "generations_after_first": len(first_generations),
        "generations_after_restart": len(generation_names(output / "state")),
        "source_preserved": True,
        "lease_released_after_each_process": True,
        "scm_installed": False,
        "production_deployment": False,
    }
    (output / "acceptance.json").write_bytes(canonical_bytes(receipt))
    return {
        "accepted": True,
        "project_id": registered.project_id,
        "snapshot_id": snapshot_id,
        "reports": 1,
        "source_preserved": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-zip", type=Path, required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--scanner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args()), ensure_ascii=False), flush=True)
