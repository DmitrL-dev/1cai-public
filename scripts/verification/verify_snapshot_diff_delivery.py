"""Verify installed dev8 CLI with owned fixtures and a real scanner; no model."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


def verify(python, scanner, output):
    python, scanner, output = (
        python.resolve(strict=True),
        scanner.resolve(strict=True),
        output.resolve(),
    )
    output.mkdir(parents=True, exist_ok=False)
    registry = output / "registry.sqlite3"
    source = output / "source"
    module = source / "CommonModules/Demo/Ext/Module.bsl"
    module.parent.mkdir(parents=True)
    before_bytes = b"Function Value() Export\nReturn 1;\nEndFunction\n"
    after_bytes = before_bytes.replace(b"1", b"2")
    module.write_bytes(before_bytes)
    (source / "Old.xml").write_bytes(b"<same/>")
    (source / "Kept.xml").write_bytes(b"<unchanged/>")
    probe = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.metadata,json,sys;from pathlib import Path;import rentgen_core;print(json.dumps({'version':importlib.metadata.version('rentgen-core'),'installed':Path(rentgen_core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())}))",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=15,
    )
    identity = json.loads(probe.stdout)
    assert identity == {"version": "0.1.0.dev8", "installed": True}, identity

    def command(name, *args, project=None, error=None):
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
        run = subprocess.run(
            argv + list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        data = json.loads(run.stdout)
        if error:
            assert run.returncode == 2 and data["error"]["code"] == error, data
            assert "result" not in data
            return data
        assert run.returncode == 0 and "error" not in data, data
        return data["result"]

    command("registry-init")
    project = command(
        "project-register",
        "--source-root",
        str(source),
        "--state-root",
        str(output / "state"),
        "--name",
        "Snapshot comparison acceptance",
    )["project_id"]
    before = command("capture", "--scanner", str(scanner), project=project)["snapshot"][
        "snapshot_id"
    ]
    module.write_bytes(after_bytes)
    (source / "Old.xml").rename(source / "New.xml")
    after = command("capture", "--scanner", str(scanner), project=project)["snapshot"][
        "snapshot_id"
    ]
    database = output / "state/state.sqlite3"
    state_before = hashlib.sha256(database.read_bytes()).hexdigest()
    registry_before = hashlib.sha256(registry.read_bytes()).hexdigest()
    head_before = command("project-head", project=project)
    selector = ("--before", before, "--after", after, "--limit", "1")
    pages = []
    page = command("snapshot-diff", *selector, project=project)
    assert page["counts"] == {"added": 1, "removed": 1, "modified": 1, "unchanged": 1}
    pages.append(page)
    cursor = page["next_cursor"]
    command(
        "snapshot-diff",
        "--before",
        after,
        "--after",
        before,
        "--limit",
        "1",
        "--cursor",
        cursor,
        project=project,
        error="INVALID_DIFF_CURSOR",
    )
    while page["next_cursor"]:
        assert len(pages) < 3, "Unexpected page loop"
        page = command(
            "snapshot-diff", *selector, "--cursor", page["next_cursor"], project=project
        )
        pages.append(page)
    changes = [change for page in pages for change in page["changes"]]
    assert [change["kind"] for change in changes] == ["modified", "added", "removed"]
    ref = changes[0]["before"]["ref"]
    ref_file = output / "before-source-ref.json"
    ref_file.write_text(json.dumps(ref), encoding="utf-8")
    retained = command(
        "source-read", "--source-ref-json", str(ref_file), "--base64", project=project
    )
    assert base64.b64decode(retained["data"], validate=True) == before_bytes
    assert command("project-head", project=project) == head_before
    assert hashlib.sha256(database.read_bytes()).hexdigest() == state_before
    assert hashlib.sha256(registry.read_bytes()).hexdigest() == registry_before
    assert module.read_bytes() == after_bytes
    report = {
        "accepted": True,
        "installed_core": identity,
        "before": before,
        "after": after,
        "counts": pages[0]["counts"],
        "pages": len(pages),
        "source_bytes_preserved": True,
        "head_and_database_preserved": True,
        "retained_source_read": True,
        "wrong_pair_cursor_rejected": True,
        "model_calls": 0,
        "scope": "Installed CLI snapshot comparison, not a continuous observer or 1C platform test",
    }
    (output / "acceptance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.python, args.scanner, args.output)))
