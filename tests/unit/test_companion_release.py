"""A release must preserve the accepted VSIX and reviewed human notes."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "companion_release", ROOT / "scripts/release/prepare_companion.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def source_repo(tmp_path, monkeypatch):
    root = tmp_path / "source"
    paths = ["integrations/vscode-rentgen", "releases/companion/0.1.4"]
    paths += [
        "integrations/open-editor/" + name
        for name in ("run_repair.py", "repair_model.py", "repair_workflow.py")
    ]
    for relative in paths:
        source, target = ROOT / relative, root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source, target, ignore=shutil.ignore_patterns("__pycache__")
            )
        else:
            shutil.copyfile(source, target)
    # Synthetic acceptance exercises the release contract as development sources
    # advance. CI separately rebuilds the real 0.1.4 from its pinned commit.
    package_path = root / "integrations/vscode-rentgen/package.json"
    package = json.loads(package_path.read_text("utf-8"))
    package["version"] = "0.1.4"
    package_path.write_text(json.dumps(package), "utf-8")
    spec = importlib.util.spec_from_file_location(
        "fixture_build", package_path.parent / "build.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    raw = builder.build_bytes()
    manifest_path = root / "releases/companion/0.1.4/manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    manifest_path.write_text(json.dumps(manifest), "utf-8")
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    for args in [
        ["init", "-b", "main"],
        ["config", "user.name", "Release fixture"],
        ["config", "user.email", "release@example.invalid"],
        ["add", "."],
        ["commit", "-m", "Accepted inputs"],
    ]:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    monkeypatch.setattr(release, "ROOT", root)
    return root


def test_wrong_version_creates_nothing(tmp_path):
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="tag must match"):
        release.build("companion-v99.0.0", output)
    assert not output.exists()


def test_release_matches_accepted_bytes_and_rejects_asset_or_note_tampering(
    tmp_path, source_repo
):
    output = tmp_path / "release"
    result = release.build("companion-v0.1.4", output)
    assert release.verify("companion-v0.1.4", output) == result
    with pytest.raises(FileExistsError):
        release.build("companion-v0.1.4", output)
    asset = output / result["asset"]
    original = asset.read_bytes()
    asset.write_bytes(original + b"changed")
    with pytest.raises(ValueError, match="accepted bytes"):
        release.verify("companion-v0.1.4", output)
    asset.write_bytes(original)
    (output / "RELEASE_NOTES.md").write_text("Ready for production", encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed source"):
        release.verify("companion-v0.1.4", output)


def test_uncommitted_release_inputs_cannot_claim_commit_provenance(
    tmp_path, source_repo
):
    (source_repo / "releases/companion/0.1.4/RELEASE_NOTES.md").write_text(
        "Changed", encoding="utf-8"
    )
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="must be committed"):
        release.build("companion-v0.1.4", output)
    assert not output.exists()


def test_release_workflow_only_creates_verified_component_drafts():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/release.yml").read_text("utf-8")
    )
    assert workflow[True]["push"]["tags"] == ["companion-v*"]
    build = workflow["jobs"]["build"]
    publish = workflow["jobs"]["draft"]
    assert build["permissions"] == {"contents": "read"}
    assert publish["needs"] == "build"
    steps = {s.get("name"): s for s in publish["steps"]}
    assert "prepare_companion.py verify" in steps["Verify downloaded assets"]["run"]
    options = steps["Create component draft"]["with"]
    assert options["draft"] is True and options["prerelease"] is True
    assert options["make_latest"] == "false"
    assert options["overwrite_files"] is False
    assert options["fail_on_unmatched_files"] is True
