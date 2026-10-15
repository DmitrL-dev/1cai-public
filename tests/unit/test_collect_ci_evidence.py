"""Exact-commit CI collection with a constructed GitHub API; no network."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "collect_ci_evidence", ROOT / "scripts/release/collect_ci_evidence.py"
)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)
SHA = "a" * 40


def archive():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr("report.xml", b"<testsuites/>")
    return stream.getvalue()


def fake(*, conclusion="success", skipped=None, digest=None, expired=False, head=SHA, body=None):
    raw = archive() if body is None else body
    api = {
        f"commits/{SHA}/check-runs?per_page=100": {
            "total_count": 2,
            "check_runs": [
                {"name": "windows", "head_sha": head, "status": "completed", "conclusion": conclusion},
                {"name": skipped or "linux", "head_sha": SHA, "status": "completed",
                 "conclusion": "skipped" if skipped else "success"},
            ],
        },
        f"actions/runs?head_sha={SHA}&per_page=100": {
            "total_count": 1,
            "workflow_runs": [{"id": 7, "name": "Product", "event": "push", "status": "completed",
                               "conclusion": "success", "run_attempt": 1, "head_sha": SHA}],
        },
        "actions/runs/7/jobs?per_page=100": {"total_count": 0, "jobs": []},
        "actions/runs/7/artifacts?per_page=100": {
            "total_count": 1,
            "artifacts": [{"id": 9, "name": "report", "size_in_bytes": len(raw),
                           "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "expired": False}],
        },
        "actions/artifacts/9": {
            "id": 9, "name": "report", "expired": expired, "size_in_bytes": len(raw),
            "digest": digest or "sha256:" + hashlib.sha256(raw).hexdigest(),
            "workflow_run": {"id": 7, "head_sha": SHA},
        },
    }
    calls = []

    def runner(argv, **kwargs):
        path = argv[2].removeprefix("repos/" + collector.REPOSITORY + "/")
        calls.append(path)
        out = raw if path == "actions/artifacts/9/zip" else json.dumps(api[path]).encode()
        return subprocess.CompletedProcess(argv, 0, out, b"")

    return runner, calls


def test_metadata_and_pinned_download_before_guarded_extraction(tmp_path):
    runner, calls = fake()
    summary = collector.metadata(SHA, tmp_path / "ci", runner=runner)
    assert summary["checks"] == {"total": 2, "success": 2, "allowed_skipped": [], "problems": []}
    pin = collector.download(tmp_path / "ci", 7, "report", runner=runner)
    assert pin["original_api_hash_size_verified_before_any_zip_parse"] is True
    assert pin["inventory"] == {
        "report.xml": {"sha256": hashlib.sha256(b"<testsuites/>").hexdigest(), "size_bytes": 13}
    }
    assert calls[-1] == "actions/artifacts/9/zip"


def test_failed_or_foreign_checks_refuse_after_saving_the_observation(tmp_path):
    runner, _ = fake(conclusion="failure")
    with pytest.raises(ValueError, match="not all successful"):
        collector.metadata(SHA, tmp_path / "ci", runner=runner)
    saved = json.loads((tmp_path / "ci/summary.json").read_text())
    assert saved["checks"]["problems"] == [
        {"name": "windows", "status": "completed", "conclusion": "failure"}
    ]
    runner, _ = fake(head="b" * 40)
    with pytest.raises(ValueError):
        collector.metadata(SHA, tmp_path / "other", runner=runner)
    runner, _ = fake(skipped="deploy")
    with pytest.raises(ValueError):
        collector.metadata(SHA, tmp_path / "skip", runner=runner)
    assert collector.metadata(SHA, tmp_path / "allowed", runner=runner, allow_skipped=("deploy",))[
        "checks"
    ]["allowed_skipped"] == ["deploy"]


@pytest.mark.parametrize(
    "options",
    [{"digest": "sha256:" + "0" * 64}, {"expired": True}, {"body": b"not a zip, wrong bytes"}],
)
def test_unpinned_or_expired_artifacts_are_never_parsed(tmp_path, options):
    good, _ = fake()
    collector.metadata(SHA, tmp_path / "ci", runner=good)
    runner, _ = fake(**options)
    if "body" in options:
        # The API pin describes other bytes than the downloaded body.
        wrong_body, api = runner, good

        def runner(argv, **kwargs):
            return (wrong_body if argv[2].endswith("/zip") else api)(argv, **kwargs)
    with pytest.raises(ValueError):
        collector.download(tmp_path / "ci", 7, "report", runner=runner)
    assert not list((tmp_path / "ci").glob("*-extracted"))
    assert not list((tmp_path / "ci").glob("*-original.zip"))


def test_inputs_are_exact():
    runner, _ = fake()
    with pytest.raises(ValueError):
        collector.metadata("HEAD", Path("/nonexistent"), runner=runner)
    with pytest.raises(ValueError):
        collector.download(Path("/nonexistent"), 7, "../escape", runner=runner)
