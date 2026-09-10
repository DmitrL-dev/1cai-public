"""Prepare an owned synthetic editor project with two different retained revisions."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

MODULE = "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"


def prepare(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source"
    shutil.copytree(args.source.resolve(strict=True), source)
    python = args.python.resolve(strict=True)
    registry = root / "registry.sqlite3"
    project = None

    def cli(command, *extra):
        argv = [
            str(python),
            "-I",
            "-m",
            "rentgen_core",
            command,
            "--registry",
            str(registry),
        ]
        if project:
            argv += ["--project", project]
        result = subprocess.run(
            argv + list(map(str, extra)), capture_output=True, timeout=60, check=True
        )
        return json.loads(result.stdout)["result"]

    def write(name, value):
        file = root / name
        file.write_text(json.dumps(value, ensure_ascii=False), "utf-8")
        return file

    cli("registry-init")
    project = cli(
        "project-register",
        "--source-root",
        source,
        "--state-root",
        root / "state",
        "--name",
        "Synthetic editor test acceptance",
    )["project_id"]
    layers = write(
        "layers.json",
        [
            {
                "layer_id": "base",
                "ordinal": 0,
                "kind": "base",
                "root_relative_path": ".",
                "source_format": "designer_xml",
            }
        ],
    )
    cli("layers-set", "--expected-revision", 1, "--layers-json", layers)
    cli("capture", "--scanner", args.scanner.resolve(strict=True))
    head = cli("project-head")
    snapshot = head["snapshot"]["snapshot_id"]
    ref = next(
        r["ref"]
        for r in cli("source-list", "--snapshot", snapshot, "--kind", "module")[
            "entries"
        ]
        if r["ref"]["relative_path"] == MODULE
    )
    ref_file = write("ref.json", ref)
    original = (source / MODULE).read_bytes()
    marker = "    Исключение\r\n".encode()
    if original.count(marker) != 1 or "ВызватьИсключение".encode() in original:
        raise ValueError("Expected bad-source from native YAxUnit verification")
    versions = [
        original.replace(marker, marker + "        ВызватьИсключение;\r\n".encode()),
        original + b"\r\n// Later version still swallows the error\r\n",
    ]
    draft, receipts = str(uuid4()), []
    for index, raw in enumerate(versions):
        replacement = root / f"replacement-{index + 1}.bsl"
        replacement.write_bytes(raw)
        proposal = cli(
            "proposal-create",
            "--snapshot",
            snapshot,
            "--source-ref-json",
            ref_file,
            "--replacement-file",
            replacement,
        )["proposal"]
        file = write(f"proposal-{index + 1}.json", proposal)
        receipts.append(
            cli(
                "draft-save",
                "--draft-id",
                draft,
                "--operation-id",
                str(uuid4()),
                "--expected-revision",
                index,
                "--snapshot",
                snapshot,
                "--proposal-json",
                file,
                "--title",
                "Проверка передачи ошибки записи",
            )
        )
    profile = cli(
        "test-profile-register",
        "--profile-json",
        args.profile_spec.resolve(strict=True),
    )
    write(
        "profile.json",
        {
            "schema": 1,
            "core_version": "0.1.0.dev8",
            "python": str(python),
            "registry": str(registry),
            "project_id": project,
        },
    )
    write(
        "tests-scenario.json",
        {
            "head": head,
            "module": MODULE,
            "selected": receipts[0],
            "latest": receipts[1],
            "profile": profile,
        },
    )
    (root / "workspace").mkdir()
    print(
        json.dumps(
            {
                "prepared": True,
                "project_id": project,
                "profile_id": profile["profile_id"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "source", "python", "scanner", "profile-spec"):
        parser.add_argument("--" + name, type=Path, required=True)
    prepare(parser.parse_args())
