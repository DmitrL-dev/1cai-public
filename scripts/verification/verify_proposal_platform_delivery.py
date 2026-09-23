"""Check installed proposals and optionally exercise live apply on owned 1C."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from verify_native_platform import PlatformRun, normalized_bsl, object_uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(
    python,
    scanner,
    platform,
    fixture,
    output,
    *,
    exercise_live=False,
    expected_core_version=None,
    expected_platform_sha256=None,
):
    python, scanner, platform, fixture = (
        p.resolve(strict=True) for p in (python, scanner, platform, fixture)
    )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    shutil.copytree(fixture, source)
    module_path = "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"
    original = (source / module_path).read_bytes()
    assert (
        b"Return 40 + 2;" in original
    ), "Use first-roundtrip from verify_native_platform.py"
    identity = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import json,sys;from importlib.metadata import version;from pathlib import Path;import rentgen_core.platform_check as p;print(json.dumps({'installed':Path(p.__file__).is_relative_to(sys.prefix),'core_version':version('rentgen-core')}))",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    installed_identity = json.loads(identity.stdout)
    assert installed_identity["installed"] is True
    assert type(installed_identity["core_version"]) is str
    if exercise_live:
        if not expected_core_version or not expected_platform_sha256:
            raise ValueError("Live verification requires pinned core and platform")
        if installed_identity["core_version"] != expected_core_version:
            raise RuntimeError("Installed core version differs from the pinned version")
        if sha(platform) != expected_platform_sha256:
            raise RuntimeError("Platform executable differs from the pinned digest")
    registry = output / "registry.sqlite3"
    project = None

    def command(name, *args, error=None):
        argv = [
            str(python),
            "-I",
            "-m",
            "rentgen_core",
            name,
            "--registry",
            str(registry),
        ]
        if project:
            argv += ["--project", project]
        # Native command owns and kills its child tree on its 600s deadline.
        completed = subprocess.run(
            argv + list(map(str, args)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=660,
        )
        data = json.loads(completed.stdout)
        if error:
            assert completed.returncode == 2 and data["error"]["code"] == error, data
            return data
        assert completed.returncode == 0 and "result" in data, data
        return data["result"]

    command("registry-init")
    project = command(
        "project-register",
        "--source-root",
        source,
        "--state-root",
        output / "state",
        "--name",
        "Native proposal acceptance",
    )["project_id"]
    layers = output / "layers.json"
    layers.write_text(
        json.dumps(
            [
                {
                    "layer_id": "base",
                    "ordinal": 0,
                    "kind": "base",
                    "root_relative_path": ".",
                    "source_format": "designer_xml",
                }
            ]
        ),
        "utf-8",
    )
    command("layers-set", "--expected-revision", "1", "--layers-json", layers)
    snapshot = command("capture", "--scanner", scanner)["snapshot"]["snapshot_id"]
    ref = command(
        "source-read",
        "--snapshot",
        snapshot,
        "--layer",
        "base",
        "--path",
        module_path,
        "--base64",
    )["ref"]
    ref_path = output / "source-ref.json"
    ref_path.write_text(json.dumps(ref), "utf-8")
    head = command("project-head")
    state_hash = sha(output / "state/state.sqlite3")
    original_files = {
        p.relative_to(source).as_posix(): sha(p)
        for p in source.rglob("*")
        if p.is_file()
    }
    reports = []
    correct_proposal_path = None
    correct_replacement = None
    for name, replacement, expected in (
        ("correct", original.replace(b"40 + 2", b"40 + 3"), "passed"),
        ("broken", original.replace(b"40 + 2", b"40 + "), "diagnostics_present"),
    ):
        replacement_path = output / (name + ".bsl")
        replacement_path.write_bytes(replacement)
        proposal = command(
            "proposal-create",
            "--snapshot",
            snapshot,
            "--source-ref-json",
            ref_path,
            "--replacement-file",
            replacement_path,
        )["proposal"]
        proposal_path = output / (name + ".proposal.json")
        proposal_path.write_text(json.dumps(proposal, ensure_ascii=False), "utf-8")
        if name == "correct":
            correct_proposal_path = proposal_path
            correct_replacement = replacement
        common = [
            "--operation-id",
            str(uuid4()),
            "--snapshot",
            snapshot,
            "--proposal-json",
            proposal_path,
            "--platform",
            platform,
        ]
        if name == "correct":
            command(
                "proposal-platform-check",
                *common,
                "--platform-sha256",
                "0" * 64,
                error="PLATFORM_BINARY_MISMATCH",
            )
        result = command(
            "proposal-platform-check", *common, "--platform-sha256", sha(platform)
        )
        assert result["analysis"]["baseline"]["status"] == "passed"
        assert result["analysis"]["candidate"]["status"] == expected
        assert result["analysis"]["candidate"]["module_text_verified"]
        assert result["source_ref"] == ref
        assert result["proposal_content_id"] == proposal["content_id"]
        assert result["candidate_sha256"] == hashlib.sha256(replacement).hexdigest()
        report_file = (
            output / "state/platform-checks" / result["run_id"] / "report.json"
        )
        assert json.loads(report_file.read_text("utf-8")) == result
        native_files = {
            p.relative_to(report_file.parent).as_posix(): (sha(p), p.stat().st_mtime_ns)
            for p in report_file.parent.rglob("*")
            if p.is_file()
        }
        repeated = command(
            "proposal-platform-check", *common, "--platform-sha256", sha(platform)
        )
        assert repeated == result
        assert {
            p.relative_to(report_file.parent).as_posix(): (sha(p), p.stat().st_mtime_ns)
            for p in report_file.parent.rglob("*")
            if p.is_file()
        } == native_files
        fetched = command(
            "proposal-platform-result", "--operation-id", result["run_id"]
        )
        assert fetched["status"] == "completed" and fetched["report"] == result
        reports.append(result)
        print(
            json.dumps({"proposal": name, "baseline": "passed", "candidate": expected}),
            flush=True,
        )
    # Only verifier-owned directories are moved, within this exclusively created
    # output. A result lookup must not need live files or retained generations.
    moves = [
        (source, output / "source-offline"),
        (output / "state/generations", output / "generations-offline"),
    ]
    moved = []
    try:
        for current, offline in moves:
            assert current.resolve().is_relative_to(
                output
            ) and offline.resolve().is_relative_to(output)
            assert not offline.exists() and not current.is_symlink()
            current.rename(offline)
            moved.append((current, offline))
        for result in reports:
            fetched = command(
                "proposal-platform-result", "--operation-id", result["run_id"]
            )
            assert fetched["report"] == result
    finally:
        for current, offline in reversed(moved):
            offline.rename(current)
    assert command("project-head") == head
    assert sha(output / "state/state.sqlite3") == state_hash
    assert {
        p.relative_to(source).as_posix(): sha(p)
        for p in source.rglob("*")
        if p.is_file()
    } == original_files
    live_result = None
    if exercise_live:
        assert correct_proposal_path is not None and correct_replacement is not None
        if source.stat().st_dev != (output / "state").stat().st_dev:
            raise RuntimeError("Live source and journal must share a filesystem")
        head_path = output / "expected-head.json"
        head_path.write_text(json.dumps(head), "utf-8")
        live_operation = str(uuid4())
        applied = command(
            "proposal-live-apply",
            "--snapshot",
            snapshot,
            "--operation-id",
            live_operation,
            "--proposal-json",
            correct_proposal_path,
            "--expected-head-json",
            head_path,
        )
        assert applied["status"] == "applied" and applied["live_source_written"] is True
        assert applied["changed_paths"] == [module_path]
        assert (source / module_path).read_bytes() == correct_replacement
        assert (
            command("proposal-live-status", "--operation-id", live_operation) == applied
        )
        native = None
        try:
            native = PlatformRun(platform, output / "native-live", timeout=120)
            native.command(
                "create", ["CREATEINFOBASE", f'File="{native.base}";Locale=ru_RU;']
            )
            native.designer("load-applied", "/LoadConfigFromFiles", source)
            native.designer(
                "check-applied",
                "/CheckConfig",
                "-Server",
                "-ExternalConnection",
                "-ThinClient",
            )
            native.designer("update-applied", "/UpdateDBCfg")
            applied_value = native.execute("execute-applied", 43)
            roundtrip = native.dump("applied-roundtrip")
            assert normalized_bsl(
                roundtrip / module_path
            ) == correct_replacement.decode("utf-8-sig").replace("\r\n", "\n")
            module_uuid = object_uuid(
                source / "CommonModules/RentgenPlatformProbe.xml", "CommonModule"
            )
            assert (
                object_uuid(
                    roundtrip / "CommonModules/RentgenPlatformProbe.xml", "CommonModule"
                )
                == module_uuid
            )
            configuration_uuid = object_uuid(
                source / "Configuration.xml", "Configuration"
            )
            assert (
                object_uuid(roundtrip / "Configuration.xml", "Configuration")
                == configuration_uuid
            )
            assert (source / module_path).read_bytes() == correct_replacement
        finally:
            undone = command("proposal-live-undo", "--operation-id", live_operation)
        assert undone["status"] == "undone"
        assert (
            command("proposal-live-status", "--operation-id", live_operation) == undone
        )
        assert (source / module_path).read_bytes() == original
        assert {
            p.relative_to(source).as_posix(): sha(p)
            for p in source.rglob("*")
            if p.is_file()
        } == original_files
        native.designer("load-undone", "/LoadConfigFromFiles", source)
        native.designer(
            "check-undone",
            "/CheckConfig",
            "-Server",
            "-ExternalConnection",
            "-ThinClient",
        )
        native.designer("update-undone", "/UpdateDBCfg")
        restored_value = native.execute("execute-undone", 42)
        restored = native.dump("undone-roundtrip")
        assert normalized_bsl(restored / module_path) == original.decode(
            "utf-8-sig"
        ).replace("\r\n", "\n")
        assert (
            object_uuid(
                restored / "CommonModules/RentgenPlatformProbe.xml", "CommonModule"
            )
            == module_uuid
        )
        assert (
            object_uuid(restored / "Configuration.xml", "Configuration")
            == configuration_uuid
        )
        assert command("project-head") == head
        live_result = {
            "operation_id": live_operation,
            "applied_result_id": applied["result_id"],
            "undone_result_id": undone["result_id"],
            "candidate_sha256": hashlib.sha256(correct_replacement).hexdigest(),
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "module_uuid": module_uuid,
            "configuration_uuid": configuration_uuid,
            "platform_executable_sha256": sha(platform),
            "runtime_values": {"applied": applied_value, "undone": restored_value},
            "native_steps": [
                {
                    "name": step["name"],
                    "exit_code": step["exit_code"],
                    "timed_out": step["timed_out"],
                }
                for step in native.steps
            ],
            "source_restored": True,
            "head_preserved": True,
        }
    report = {
        "accepted": True,
        "installed": True,
        "core_version": installed_identity["core_version"],
        "native_checks": len(reports),
        "candidate_statuses": [r["analysis"]["candidate"]["status"] for r in reports],
        "report_ids": [r["run_id"] for r in reports],
        "head_and_state_preserved": True,
        "live_sources_preserved": True,
        "wrong_executable_hash_refused": True,
        "completed_replay_preserves_all_native_files": True,
        "result_lookup_without_sources_or_generations": True,
        "model_calls": 0,
        "application_execution": False,
    }
    if live_result is not None:
        report["live_apply_native"] = live_result
        report["application_execution"] = True
    (output / "acceptance.json").write_text(json.dumps(report, indent=2), "utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "scanner", "platform", "fixture", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--exercise-live", action="store_true")
    parser.add_argument("--expected-core-version")
    parser.add_argument("--expected-platform-sha256")
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.python,
                args.scanner,
                args.platform,
                args.fixture,
                args.output,
                exercise_live=args.exercise_live,
                expected_core_version=args.expected_core_version,
                expected_platform_sha256=args.expected_platform_sha256,
            )
        )
    )
