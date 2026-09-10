"""Check installed proposals against a native fixture, without executing its BSL."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(python, scanner, platform, fixture, output):
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
            "import json,sys;from pathlib import Path;import rentgen_core.platform_check as p;print(json.dumps({'installed':Path(p.__file__).is_relative_to(sys.prefix)}))",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(identity.stdout) == {"installed": True}
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
        common = [
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
        reports.append(result)
        print(
            json.dumps({"proposal": name, "baseline": "passed", "candidate": expected}),
            flush=True,
        )
    assert command("project-head") == head
    assert sha(output / "state/state.sqlite3") == state_hash
    assert {
        p.relative_to(source).as_posix(): sha(p)
        for p in source.rglob("*")
        if p.is_file()
    } == original_files
    report = {
        "accepted": True,
        "installed": True,
        "native_checks": len(reports),
        "candidate_statuses": [r["analysis"]["candidate"]["status"] for r in reports],
        "report_ids": [r["run_id"] for r in reports],
        "head_and_state_preserved": True,
        "live_sources_preserved": True,
        "wrong_executable_hash_refused": True,
        "model_calls": 0,
        "application_execution": False,
    }
    (output / "acceptance.json").write_text(json.dumps(report, indent=2), "utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "scanner", "platform", "fixture", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.python, args.scanner, args.platform, args.fixture, args.output)
        )
    )
