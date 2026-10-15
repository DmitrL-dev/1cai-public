"""Collect exact-commit CI metadata and API-pinned original artifacts.

`metadata` saves the GitHub check-run, workflow-run, job and artifact listings
for one exact commit and refuses unless every check completed successfully
(an explicitly allowed check name may be skipped). `download` streams one listed
artifact, verifies the GitHub API size and SHA256 before any ZIP parse, then
extracts it through the production guard into a new directory.

The collector records observations; it never creates qualification or
publication records, tags or releases. Reducers judge content separately.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "DmitrL-dev/1cai-public"
SHA = re.compile(r"[0-9a-f]{40}")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
MAX_ARTIFACT = 512 * 1024**2
MAX_JSON = 32 * 1024**2


def _gh(path, *, raw=False, runner=subprocess.run):
    result = runner(
        ["gh", "api", "repos/" + REPOSITORY + "/" + path],
        capture_output=True,
        timeout=180,
        check=True,
    )
    if raw:
        return result.stdout
    if len(result.stdout) > MAX_JSON:
        raise ValueError("GitHub API response exceeds bound")
    return json.loads(result.stdout)


def _save(directory, name, value):
    path = Path(directory) / name
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
    return path


def metadata(sha, output, *, allow_skipped=(), runner=subprocess.run):
    """Save exact-commit CI listings; refuse unless every check succeeded."""
    if not SHA.fullmatch(sha):
        raise ValueError("Exact lowercase 40-hex commit SHA required")
    output = Path(output)
    output.mkdir(mode=0o700)
    checks = _gh(f"commits/{sha}/check-runs?per_page=100", runner=runner)
    runs = _gh(f"actions/runs?head_sha={sha}&per_page=100", runner=runner)
    if checks["total_count"] != len(checks["check_runs"]) or not checks["check_runs"]:
        raise ValueError("Incomplete or empty check-run listing")
    if runs["total_count"] != len(runs["workflow_runs"]) or not runs["workflow_runs"]:
        raise ValueError("Incomplete or empty workflow-run listing")
    problems = [
        {"name": c["name"], "status": c["status"], "conclusion": c["conclusion"]}
        for c in checks["check_runs"]
        if c["head_sha"] != sha
        or c["status"] != "completed"
        or not (
            c["conclusion"] == "success"
            or c["conclusion"] == "skipped" and c["name"] in allow_skipped
        )
    ]
    _save(output, "check-runs-api.json", checks)
    _save(output, "workflow-runs-api.json", runs)
    workflows = {}
    for run in runs["workflow_runs"]:
        if run["head_sha"] != sha:
            raise ValueError("Workflow run is bound to another commit")
        jobs = _gh(f"actions/runs/{run['id']}/jobs?per_page=100", runner=runner)
        artifacts = _gh(f"actions/runs/{run['id']}/artifacts?per_page=100", runner=runner)
        if jobs["total_count"] != len(jobs["jobs"]):
            raise ValueError("Incomplete job listing")
        if artifacts["total_count"] != len(artifacts["artifacts"]):
            raise ValueError("Incomplete artifact listing")
        _save(output, f"run-{run['id']}-jobs-api.json", jobs)
        _save(output, f"run-{run['id']}-artifacts-api.json", artifacts)
        workflows[str(run["id"])] = {
            "name": run["name"],
            "event": run["event"],
            "status": run["status"],
            "conclusion": run["conclusion"],
            "run_attempt": run["run_attempt"],
            "artifacts": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "size_in_bytes": a["size_in_bytes"],
                    "digest": a.get("digest"),
                    "expired": a["expired"],
                }
                for a in artifacts["artifacts"]
            ],
        }
    summary = {
        "schema": 1,
        "kind": "exact-commit CI observation; not a qualification receipt",
        "repository": REPOSITORY,
        "head_sha": sha,
        "checks": {
            "total": len(checks["check_runs"]),
            "success": sum(c["conclusion"] == "success" for c in checks["check_runs"]),
            "allowed_skipped": sorted(
                c["name"] for c in checks["check_runs"] if c["conclusion"] == "skipped"
            ),
            "problems": problems,
        },
        "workflows": workflows,
    }
    _save(output, "summary.json", summary)
    if problems:
        raise ValueError("Exact-commit checks are not all successful")
    return summary


def _guard():
    spec = importlib.util.spec_from_file_location(
        "rentgen_release_archive_guard",
        ROOT / "scripts/verification/editor_workbench/archive.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def download(evidence, run_id, name, *, runner=subprocess.run):
    """Download one listed artifact; pin API size/SHA256 before any ZIP parse."""
    evidence = Path(evidence)
    if not NAME.fullmatch(name) or type(run_id) is not int:
        raise ValueError("Exact artifact name and run ID required")
    summary = json.loads((evidence / "summary.json").read_text("utf-8"))
    listed = [
        a for a in summary["workflows"][str(run_id)]["artifacts"] if a["name"] == name
    ]
    if len(listed) != 1:
        raise ValueError("Artifact is not listed exactly once for this run")
    artifact = _gh(f"actions/artifacts/{listed[0]['id']}", runner=runner)
    if (
        artifact["id"] != listed[0]["id"]
        or artifact["expired"] is not False
        or artifact["workflow_run"]["id"] != run_id
        or artifact["workflow_run"]["head_sha"] != summary["head_sha"]
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.get("digest") or "")
        or type(artifact["size_in_bytes"]) is not int
        or not 0 < artifact["size_in_bytes"] <= MAX_ARTIFACT
    ):
        raise ValueError("Artifact API record is not an exact unexpired pin")
    expected, size = artifact["digest"][7:], artifact["size_in_bytes"]
    raw = _gh(f"actions/artifacts/{artifact['id']}/zip", raw=True, runner=runner)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Downloaded bytes differ from the GitHub API pin")
    original = evidence / f"{name}-{artifact['id']}-original.zip"
    with original.open("xb") as stream:
        stream.write(raw)
    # No ZIP read occurs before the size/hash gate above.
    inventory = _guard().extract_verified(
        original, evidence / f"{name}-{artifact['id']}-extracted", sha256=expected, size_bytes=size
    )
    pin = {
        "artifact_id": artifact["id"],
        "name": name,
        "run_id": run_id,
        "head_sha": summary["head_sha"],
        "sha256": expected,
        "size_bytes": size,
        "original_api_hash_size_verified_before_any_zip_parse": True,
        "guarded_extraction_files": len(inventory),
        "inventory": inventory,
    }
    _save(evidence, f"{name}-{artifact['id']}-pin.json", pin)
    return pin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    meta = commands.add_parser("metadata")
    meta.add_argument("--sha", required=True)
    meta.add_argument("--output", type=Path, required=True)
    meta.add_argument("--allow-skipped", action="append", default=[])
    get = commands.add_parser("download")
    get.add_argument("--evidence", type=Path, required=True)
    get.add_argument("--run-id", type=int, required=True)
    get.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "metadata":
            value = metadata(args.sha, args.output, allow_skipped=tuple(args.allow_skipped))
        else:
            value = download(args.evidence, args.run_id, args.name)
    except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": type(exc).__name__, "reason": str(exc)[:240]}))
        return 1
    print(json.dumps({k: v for k, v in value.items() if k != "inventory"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
