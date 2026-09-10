"""Accepted release inputs and artifact bytes must agree before publication."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_core",
    Path(__file__).resolve().parents[2] / "scripts/release/prepare_core.py",
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def accepted(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root).decode().strip()

    git("init", "-q")
    git("config", "user.name", "Release contract fixture")
    git("config", "user.email", "test@example.invalid")
    (root / "source.txt").write_bytes(b"fixture only")
    git("add", ".")
    git("commit", "-qm", "Source fixture")
    commit = git("rev-parse", "HEAD")
    version = "0.1.0.dev8"
    name = "rentgen-core-" + version + "-windows-py311.zip"
    kit = tmp_path / name
    wheel, sdist = b"fixture wheel", b"fixture sdist"
    with ZipFile(kit, "w") as archive:
        prefix = name[:-4] + "/"
        archive.writestr(
            prefix + "build-input-hashes.json", json.dumps({"source_commit": commit})
        )
        archive.writestr(
            prefix + "rentgen_core-" + version + "-py3-none-any.whl", wheel
        )
        archive.writestr(prefix + "rentgen_core-" + version + ".tar.gz", sdist)
    folder = root / "releases/core" / version
    folder.mkdir(parents=True)
    manifest = {
        "version": version,
        "tag": "core-v0.1.0-dev8",
        "asset": name,
        "prerelease": True,
        "full_product_ready": False,
        "size_bytes": kit.stat().st_size,
        "sha256": release.digest(kit),
        "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
        "sdist_sha256": hashlib.sha256(sdist).hexdigest(),
        "source_commit": commit,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    (folder / "RELEASE_NOTES.md").write_bytes(b"Reviewed fixture notes")
    git("add", ".")
    git("commit", "-qm", "Accepted release metadata")
    monkeypatch.setattr(release, "ROOT", root)
    return version, kit, tmp_path / "release", folder


def test_prepare_and_verify_preserve_accepted_bytes(accepted):
    version, kit, output, _ = accepted
    assert release.prepare(version, kit, output)["verified"]
    assert release.verify(version, output)["verified"]
    with pytest.raises(FileExistsError):
        release.prepare(version, kit, output)
    (output / kit.name).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="accepted bytes"):
        release.verify(version, output)


def test_uncommitted_notes_and_unexpected_assets_refused(accepted):
    version, kit, output, folder = accepted
    release.prepare(version, kit, output)
    (output / "extra").write_bytes(b"unreviewed")
    with pytest.raises(ValueError, match="inventory"):
        release.verify(version, output)
    (folder / "RELEASE_NOTES.md").write_bytes(b"not reviewed")
    with pytest.raises(ValueError, match="committed"):
        release.prepare(version, kit, output.parent / "new")


def test_version_path_cannot_escape_release_records():
    with pytest.raises(ValueError, match="version"):
        release.inputs("../../elsewhere")
