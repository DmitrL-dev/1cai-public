"""Release notes and tags must agree with real Git history."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_notes",
    Path(__file__).resolve().parents[2] / "scripts/release/create_release.py",
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(
            ["git", *args], text=True, encoding="utf-8", stderr=subprocess.PIPE
        ).strip()

    git("init", "-b", "main")
    git("config", "user.name", "Release fixture")
    git("config", "user.email", "release@example.invalid")
    (tmp_path / "source.txt").write_text("first", encoding="utf-8")
    git("add", "source.txt")
    git("commit", "-m", "First implementation")
    git("tag", "v1.0.0")
    (tmp_path / "source.txt").write_text("second", encoding="utf-8")
    git("commit", "-am", "Actual second change")
    return git


def test_current_release_tag_is_excluded_from_the_previous_tag(repo):
    repo("tag", "v1.1.0")
    assert release.main(["--version", "v1.1.0", "--no-append"]) == 0
    notes = Path("RELEASE_NOTES.md").read_text("utf-8")
    assert "Actual second change" in notes
    assert "First implementation" not in notes


def test_regenerating_a_version_preserves_history_without_duplicate_sections(repo):
    Path("RELEASE_NOTES.md").write_text(
        "## v1.0.0 — earlier\n\nOld notes.\n", encoding="utf-8"
    )
    release.main(["--version", "v1.1.0"])
    first = Path("RELEASE_NOTES.md").read_bytes()
    release.main(["--version", "v1.1.0"])
    assert Path("RELEASE_NOTES.md").read_bytes() == first
    assert b"Old notes." in first


def test_tag_requires_committed_notes_and_never_rewrites_them(repo):
    release.main(["--version", "v1.1.0"])
    with pytest.raises(ValueError, match="clean"):
        release.main(["--version", "v1.1.0", "--tag"])
    assert repo("tag", "--list", "v1.1.0") == ""
    repo("add", "RELEASE_NOTES.md")
    repo("commit", "-m", "Record reviewed release notes")
    before = Path("RELEASE_NOTES.md").read_bytes()
    assert release.main(["--version", "v1.1.0", "--tag"]) == 0
    assert repo("cat-file", "-t", "refs/tags/v1.1.0") == "tag"
    assert repo("rev-parse", "v1.1.0^{commit}") == repo("rev-parse", "HEAD")
    assert Path("RELEASE_NOTES.md").read_bytes() == before


def test_invalid_version_or_implicit_push_remote_has_no_side_effects(repo):
    for args in [["--version", "--all"], ["--version", "v1.1.0", "--push"]]:
        with pytest.raises(SystemExit):
            release.main(args)
    assert not Path("RELEASE_NOTES.md").exists()
    assert repo("tag", "--list") == "v1.0.0"


def test_stable_notes_do_not_remove_the_prerelease_section(repo):
    Path("RELEASE_NOTES.md").write_text(
        "## v1.1.0-rc1 — earlier\n\nKeep prerelease history.\n", encoding="utf-8"
    )
    release.main(["--version", "v1.1.0"])
    assert "Keep prerelease history." in Path("RELEASE_NOTES.md").read_text("utf-8")
