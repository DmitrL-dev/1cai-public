"""Verify installed profile registration, native proposal tests and result recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
MODULE = "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"


def verify(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    python = args.python.resolve(strict=True)
    source = output / "source"
    shutil.copytree(args.source.resolve(strict=True), source)
    original = (source / MODULE).read_bytes()
    marker = "    Исключение\r\n".encode()
    if original.count(marker) != 1 or "ВызватьИсключение".encode() in original:
        raise ValueError("Use bad-source from verify_yaxunit_platform.py")
    identity = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import json,sys,importlib.metadata;from pathlib import Path;import rentgen_core.test_execution as t;print(json.dumps({'installed':Path(t.__file__).is_relative_to(sys.prefix),'version':importlib.metadata.version('rentgen-core')}))",
        ],
        timeout=15,
    )
    if json.loads(identity) != {"installed": True, "version": "0.1.0.dev8"}:
        raise ValueError("Installed dev8 required")
    registry = output / "registry.sqlite3"
    project, sequence = None, 0

    def command(name, *extra, error=None):
        nonlocal sequence
        sequence += 1
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
        process = subprocess.Popen(
            argv + list(map(str, extra)), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = process.communicate(
                timeout=1000 if name == "proposal-test" else 60
            )
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
            process.communicate(timeout=15)
            raise
        (output / f"{sequence:02d}-{name}.stdout").write_bytes(stdout)
        (output / f"{sequence:02d}-{name}.stderr").write_bytes(stderr)
        value = json.loads(stdout)
        if error:
            assert process.returncode == 2 and value["error"]["code"] == error, value
            return value
        assert process.returncode == 0 and "result" in value, value
        return value["result"]

    command("registry-init")
    project = command(
        "project-register",
        "--source-root",
        source,
        "--state-root",
        output / "state",
        "--name",
        "Installed YAxUnit proposal acceptance",
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
    command("layers-set", "--expected-revision", 1, "--layers-json", layers)
    command("capture", "--scanner", args.scanner.resolve(strict=True))
    head = command("project-head")
    snapshot = head["snapshot"]["snapshot_id"]
    ref = command("source-list", "--snapshot", snapshot, "--kind", "module")["entries"]
    selected = next(row["ref"] for row in ref if row["ref"]["relative_path"] == MODULE)
    ref_file = output / "ref.json"
    ref_file.write_text(json.dumps(selected), "utf-8")
    replacement = output / "replacement.bsl"
    replacement.write_bytes(
        original.replace(marker, marker + "        ВызватьИсключение;\r\n".encode())
    )
    proposal = command(
        "proposal-create",
        "--snapshot",
        snapshot,
        "--source-ref-json",
        ref_file,
        "--replacement-file",
        replacement,
    )["proposal"]
    proposal_file = output / "proposal.json"
    proposal_file.write_text(json.dumps(proposal), "utf-8")

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    specification = {
        "schema": 1,
        "name": "Ошибка записи передаётся вызывающему коду",
        "platform": {
            "path": str(args.platform.resolve(strict=True)),
            "sha256": args.platform_sha256,
        },
        "ibcmd": {
            "path": str(args.ibcmd.resolve(strict=True)),
            "sha256": args.ibcmd_sha256,
        },
        "engine": {
            "path": str(args.cfe.resolve(strict=True)),
            "sha256": "805a2277c997a3c24be0b0d080696479e91e4a15ed7e27aaf3991a7346522d70",
        },
        "modules": [
            {
                "name": "ЮТРентгенПроверка",
                "path": str(
                    ROOT / "packaging/test-profiles/yaxunit-25.12/ОшибкаЗаписи.bsl"
                ),
                "tests": ["ОшибкаЗаписиПередается"],
            }
        ],
    }
    specification_file = output / "test-profile.json"
    specification_file.write_text(
        json.dumps(specification, ensure_ascii=False), "utf-8"
    )
    profile = command("test-profile-register", "--profile-json", specification_file)
    assert (
        command("test-profile-register", "--profile-json", specification_file)
        == profile
    )
    assert command("test-profile-list") == [profile]
    operation = str(uuid4())
    (output / "operation.json").write_text(
        json.dumps(
            {
                "project_id": project,
                "operation_id": operation,
                "profile_id": profile["profile_id"],
            }
        ),
        "utf-8",
    )
    (source / MODULE).write_bytes(b"Live source changed after snapshot\n")
    result = command(
        "proposal-test",
        "--snapshot",
        snapshot,
        "--proposal-json",
        proposal_file,
        "--test-profile",
        profile["profile_id"],
        "--operation-id",
        operation,
    )
    assert result["tests"]["baseline"]["status"] == "failed", result
    assert result["tests"]["candidate"]["status"] == "passed", result
    assert result["tests"]["candidate"]["counts"]["passed"] == 1
    assert result["tests"]["isolated_infobases"] is True
    assert result["candidate_sha256"] == digest(replacement)
    assert result["proposal_content_id"] == proposal["content_id"]
    assert (
        command("proposal-test-result", "--operation-id", operation)["report"] == result
    )
    command("test-profile-disable", "--profile-id", profile["profile_id"])
    run = output / "state/test-runs" / operation
    before = {str(p.relative_to(run)): digest(p) for p in run.rglob("*") if p.is_file()}
    assert (
        command(
            "proposal-test",
            "--snapshot",
            snapshot,
            "--proposal-json",
            proposal_file,
            "--test-profile",
            profile["profile_id"],
            "--operation-id",
            operation,
        )
        == result
    )
    assert {
        str(p.relative_to(run)): digest(p) for p in run.rglob("*") if p.is_file()
    } == before
    command(
        "proposal-test",
        "--snapshot",
        snapshot,
        "--proposal-json",
        proposal_file,
        "--test-profile",
        profile["profile_id"],
        "--operation-id",
        str(uuid4()),
        error="TEST_PROFILE_DISABLED",
    )
    assert command("project-head") == head
    assert (source / MODULE).read_bytes() == b"Live source changed after snapshot\n"
    evidence = {
        "accepted": True,
        "result": result,
        "profile": profile,
        "completed_replay_without_changes": True,
        "disabled_new_run_refused": True,
        "live_source_and_head_preserved": True,
        "installed": json.loads(identity),
    }
    (output / "acceptance.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), "utf-8"
    )
    return {
        "accepted": True,
        "operation_id": operation,
        "profile_id": profile["profile_id"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "scanner", "source", "platform", "ibcmd", "cfe", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("platform-sha256", "ibcmd-sha256"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(verify(parser.parse_args())))
