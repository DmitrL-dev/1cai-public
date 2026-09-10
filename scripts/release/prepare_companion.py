"""Build or verify a companion prerelease against its committed acceptance hash."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def inputs(tag):
    package = json.loads(
        (ROOT / "integrations/vscode-rentgen/package.json").read_text("utf-8")
    )
    version = package["version"]
    if (
        not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
        or tag != "companion-v" + version
    ):
        raise ValueError("Release tag must match the companion version")
    record = ROOT / "releases/companion" / version
    manifest = json.loads((record / "manifest.json").read_text("utf-8"))
    if manifest["version"] != version or manifest["stage"] != "prerelease":
        raise ValueError("Expected an accepted component prerelease")
    return version, manifest, (record / "RELEASE_NOTES.md").read_bytes()


def digest(file):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_commit(version):
    paths = ["integrations/vscode-rentgen", "releases/companion/" + version]
    paths += [
        "integrations/open-editor/" + name
        for name in ("run_repair.py", "repair_model.py", "repair_workflow.py")
    ]
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        cwd=ROOT,
    )
    if dirty:
        raise ValueError(
            "Release inputs must be committed before building or verifying"
        )
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def verify(tag, output):
    version, manifest, notes = inputs(tag)
    name = "rentgen-companion-" + version + ".vsix"
    if {p.name for p in output.iterdir()} != {
        name,
        "SHA256SUMS",
        "RELEASE_NOTES.md",
        "release.json",
    }:
        raise ValueError("Unexpected or missing release assets")
    file = output / name
    if (
        file.stat().st_size != manifest["size_bytes"]
        or digest(file) != manifest["sha256"]
    ):
        raise ValueError("Release asset differs from accepted bytes")
    if (output / "RELEASE_NOTES.md").read_bytes() != notes:
        raise ValueError("Release notes differ from the reviewed source")
    if (output / "SHA256SUMS").read_text("ascii") != f"{manifest['sha256']}  {name}\n":
        raise ValueError("Unexpected release checksum file")
    metadata = json.loads((output / "release.json").read_text("utf-8"))
    commit = source_commit(version)
    if metadata != {**manifest, "source_commit": commit, "tag": tag, "asset": name}:
        raise ValueError("Release provenance does not match this checkout")
    return metadata


def build(tag, output):
    version, manifest, notes = inputs(tag)
    commit = source_commit(version)
    spec = importlib.util.spec_from_file_location(
        "companion_builder", ROOT / "integrations/vscode-rentgen/build.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    raw = builder.build_bytes()
    if (
        len(raw) != manifest["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != manifest["sha256"]
    ):
        raise ValueError(
            "Build differs from the accepted companion; review a new version"
        )
    output.mkdir(parents=True, exist_ok=False)
    name = "rentgen-companion-" + version + ".vsix"
    (output / name).write_bytes(raw)
    (output / "RELEASE_NOTES.md").write_bytes(notes)
    (output / "SHA256SUMS").write_text(
        f"{manifest['sha256']}  {name}\n", encoding="ascii", newline="\n"
    )
    metadata = {**manifest, "source_commit": commit, "tag": tag, "asset": name}
    (output / "release.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return verify(tag, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "verify"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (build if args.mode == "build" else verify)(args.tag, args.output)
    print(json.dumps(result))
