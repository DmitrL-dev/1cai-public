"""Prepare immutable core release assets from a committed, accepted CI kit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inputs(version):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.dev[0-9]+", version):
        raise ValueError("Explicit development core version required")
    folder = ROOT / "releases/core" / version
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    expected = "rentgen-core-" + version + "-windows-py311.zip"
    if (
        manifest.get("version") != version
        or manifest.get("asset") != expected
        or manifest.get("tag") != "core-v" + version.replace(".dev", "-dev")
        or manifest.get("prerelease") is not True
        or manifest.get("full_product_ready") is not False
        or type(manifest.get("size_bytes")) is not int
        or not 0 < manifest["size_bytes"] <= 256 * 1024**2
    ):
        raise ValueError("Invalid accepted core manifest")
    for key, length in (
        ("sha256", 64),
        ("wheel_sha256", 64),
        ("sdist_sha256", 64),
        ("source_commit", 40),
    ):
        if not re.fullmatch("[0-9a-f]{" + str(length) + "}", manifest.get(key, "")):
            raise ValueError("Invalid accepted digest or source commit")
    dirty = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--",
            str(folder),
            "scripts/release/prepare_core.py",
        ],
        cwd=ROOT,
    )
    if dirty:
        raise ValueError("Release inputs must be committed")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", manifest["source_commit"], "HEAD"],
        cwd=ROOT,
        capture_output=True,
    ).returncode:
        raise ValueError("Accepted source commit must be available in checkout history")
    return (
        manifest,
        (folder / "manifest.json").read_bytes(),
        (folder / "RELEASE_NOTES.md").read_bytes(),
    )


def verify_kit(kit, manifest):
    if (
        kit.stat().st_size != manifest["size_bytes"]
        or digest(kit) != manifest["sha256"]
    ):
        raise ValueError("Kit differs from accepted bytes")
    prefix = manifest["asset"][:-4] + "/"
    with ZipFile(kit) as archive:
        name = prefix + "build-input-hashes.json"
        if archive.getinfo(name).file_size > 65536:
            raise ValueError("Build provenance exceeds limit")
        metadata = json.loads(archive.read(name))
        if metadata.get("source_commit") != manifest["source_commit"]:
            raise ValueError("Kit source commit differs from accepted provenance")
        for suffix, key in (
            ("-py3-none-any.whl", "wheel_sha256"),
            (".tar.gz", "sdist_sha256"),
        ):
            name = prefix + "rentgen_core-" + manifest["version"] + suffix
            with archive.open(name) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != manifest[key]:
                    raise ValueError("Core build output differs from accepted digest")


def verify(version, output):
    manifest, raw, notes = inputs(version)
    if {p.name for p in output.iterdir()} != {
        manifest["asset"],
        "manifest.json",
        "SHA256SUMS",
        "RELEASE_NOTES.md",
    }:
        raise ValueError("Unexpected release inventory")
    if (output / "manifest.json").read_bytes() != raw or (
        output / "RELEASE_NOTES.md"
    ).read_bytes() != notes:
        raise ValueError("Release metadata differs from committed inputs")
    if (output / "SHA256SUMS").read_bytes() != (
        manifest["sha256"] + "  " + manifest["asset"] + "\n"
    ).encode("ascii"):
        raise ValueError("Release checksum differs from accepted digest")
    verify_kit(output / manifest["asset"], manifest)
    return {
        "verified": True,
        "tag": manifest["tag"],
        "source_commit": manifest["source_commit"],
        "sha256": manifest["sha256"],
    }


def prepare(version, kit, output):
    manifest, raw, notes = inputs(version)
    verify_kit(kit, manifest)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(kit, output / manifest["asset"])
    (output / "manifest.json").write_bytes(raw)
    (output / "RELEASE_NOTES.md").write_bytes(notes)
    (output / "SHA256SUMS").write_bytes(
        (manifest["sha256"] + "  " + manifest["asset"] + "\n").encode("ascii")
    )
    return verify(version, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "verify"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--kit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare" and args.kit is None:
        parser.error("prepare requires --kit")
    print(
        json.dumps(
            prepare(args.version, args.kit, args.output)
            if args.mode == "prepare"
            else verify(args.version, args.output)
        )
    )
