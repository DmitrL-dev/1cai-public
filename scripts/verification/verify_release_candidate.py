"""Collect exact successful CI bytes, then qualify a Linux candidate without credentials.

This tool never accepts release records, changes refs or publishes. Collection
requires a read-only GitHub token. Qualification is a separate credential-free
process and uses the canonical Windows wheel, never a local package rebuild.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import tomllib
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET
import zipfile

from kit_inputs import extract, member_path
from verify_service_scm_delivery import validate_provenance, unpack

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "DmitrL-dev/1cai-public"
API = "https://api.github.com/repos/" + REPOSITORY
MAX_WRAPPER = 128 * 1024**2
MAX_JSON = 2 * 1024**2


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    require(path.stat().st_size <= MAX_JSON, "JSON receipt exceeds limit")
    return json.loads(path.read_text("utf-8"))


def save(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    require(len(raw) <= MAX_JSON, "JSON receipt exceeds limit")
    path.write_bytes(raw)


def packager():
    spec = importlib.util.spec_from_file_location(
        "candidate_packager", ROOT / "scripts/release/prepare_experimental_linux.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_source(source):
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source),
            "Source must be an exact lowercase commit SHA")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(actual == source, "Checkout differs from requested source")
    require(subprocess.run(["git", "diff", "--quiet", source, "--"], cwd=ROOT,
                           capture_output=True).returncode == 0,
            "Tracked checkout bytes differ from requested source")
    require(subprocess.run(["git", "merge-base", "--is-ancestor", source,
                            "refs/remotes/origin/main"], cwd=ROOT,
                           capture_output=True).returncode == 0,
            "Requested source must be reachable from fetched upstream main")
    return subprocess.check_output(["git", "rev-parse", source + "^{tree}"],
                                   cwd=ROOT, text=True).strip()


def validate_run(run, run_id, source, workflow_path):
    require(type(run_id) is int and run_id > 0 and run.get("id") == run_id,
            "Unexpected CI run identity")
    require(run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("head_repository", {}).get("full_name") == REPOSITORY,
            "CI must belong to the intended repository")
    require(run.get("path") == workflow_path and run.get("head_sha") == source,
            "CI workflow or exact source differs")
    require(run.get("event") == "push" and run.get("head_branch") == "main",
            "CI must qualify a main push")
    require(run.get("status") == "completed" and run.get("conclusion") == "success",
            "CI must be completed and successful")
    require(type(run.get("run_attempt")) is int and run["run_attempt"] > 0,
            "Missing CI attempt identity")
    return {key: run[key] for key in ("id", "head_sha", "path", "run_attempt", "updated_at")}


def select_artifact(response, name, run_id, source):
    items = response.get("artifacts", [])
    require(response.get("total_count") == len(items) and len(items) <= 100,
            "Artifact listing is incomplete or oversized")
    matches = [item for item in items if item.get("name") == name]
    require(len(matches) == 1, "Expected one exact CI artifact")
    item = matches[0]
    require(item.get("expired") is False
            and type(item.get("id")) is int and item["id"] > 0,
            "Artifact is expired or lacks identity")
    require(type(item.get("size_in_bytes")) is int
            and 0 < item["size_in_bytes"] <= MAX_WRAPPER,
            "Artifact wrapper exceeds size limit")
    require(isinstance(item.get("digest"), str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]),
            "Missing trusted artifact digest")
    require(item.get("workflow_run", {}).get("id") == run_id
            and item["workflow_run"].get("head_sha") == source,
            "Artifact does not belong to the exact CI source")
    return item


def verify_download(path, artifact):
    require(path.stat().st_size == artifact["size_in_bytes"]
            and "sha256:" + sha(path) == artifact["digest"],
            "Downloaded artifact differs from API size/digest")


def wheel_members(path):
    """Compare package bytes independently of platform ZIP timestamps/modes."""
    require(0 < path.stat().st_size <= 64 * 1024**2, "Wheel container exceeds limit")
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        require(0 < len(members) <= 4096, "Wheel member count exceeds limit")
        for member in members:
            name = member.orig_filename
            member_path(name, ROOT / "output/wheel-inventory", seen)
            require(stat.S_IFMT(member.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR),
                    "Wheel contains a special file")
            require(0 <= member.file_size <= 64 * 1024**2, "Wheel member exceeds limit")
            total += member.file_size
            require(total <= MAX_WRAPPER, "Expanded wheel exceeds limit")
            with archive.open(member) as stream:
                raw = stream.read(64 * 1024**2 + 1)
            require(len(raw) == member.file_size and (not member.is_dir() or not raw),
                    "Wheel member size differs")
            files[name] = raw
    return files


class NoAuthRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        require(parts.scheme == "https" and not parts.username and not parts.password,
                "Artifact redirect must use HTTPS without credentials")
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, token):
        require(bool(token), "Collection requires a read-only GH_TOKEN")
        self.token = token
        self.opener = build_opener(NoAuthRedirect())

    def request(self, path):
        require(path.startswith("/") and not path.startswith("//"), "Invalid API path")
        request = Request(API + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            return self.opener.open(request, timeout=30)
        except URLError:
            raise ValueError("GitHub request failed; no candidate accepted") from None

    def json(self, path):
        with self.request(path) as response:
            raw = response.read(MAX_JSON + 1)
        require(len(raw) <= MAX_JSON, "GitHub JSON response exceeds limit")
        return json.loads(raw)

    def download(self, artifact, destination):
        deadline = time.monotonic() + 180
        with self.request(f"/actions/artifacts/{artifact['id']}/zip") as response, destination.open("xb") as stream:
            total = 0
            while chunk := response.read(65536):
                total += len(chunk)
                require(total <= artifact["size_in_bytes"] <= MAX_WRAPPER,
                        "Artifact download exceeds API size")
                require(time.monotonic() < deadline, "Artifact download deadline exceeded")
                stream.write(chunk)
        verify_download(destination, artifact)


def collect(source, product_run, portable_run, output, api):
    tree = bind_source(source)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    paths = {"product": (product_run, ".github/workflows/core-ci.yml", "verified-core-development"),
             "portable": (portable_run, ".github/workflows/portable-ci.yml", "experimental-linux-python-3.11")}
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    for key, (run_id, workflow, name) in paths.items():
        run = validate_run(api.json(f"/actions/runs/{run_id}"), run_id, source, workflow)
        artifact = select_artifact(api.json(f"/actions/runs/{run_id}/artifacts?per_page=100"),
                                   name, run_id, source)
        archive = output / (key + ".zip")
        api.download(artifact, archive)
        verify_download(archive, artifact)  # No extraction before the independent digest check.
        extract(archive, output / key)
        records[key] = {"run": run, "artifact": {k: artifact[k] for k in
                        ("id", "name", "digest", "size_in_bytes")}}
    windows = output / "product/core-kit"
    kit = windows / f"rentgen-core-{version}-windows-py311.zip"
    receipt = read_json(windows / "acceptance.json")
    kit_hash = validate_provenance(kit, receipt, source)
    kit_root, wheel, inventory = unpack(kit, output / "windows-kit", source, receipt)
    require(inventory.get("version") == version
            and kit_root.name == kit.stem
            and wheel.name == f"rentgen_core-{version}-py3-none-any.whl",
            "Windows kit version/layout differs from exact source")
    sdist = kit_root / f"rentgen_core-{version}.tar.gz"
    require(sha(sdist) == receipt["kit"]["sdist_sha256"], "Windows sdist hash differs")
    linux = output / "portable"
    linux_wheel = linux / "dist" / wheel.name
    canonical_members = wheel_members(wheel)
    require(wheel_members(linux_wheel) == canonical_members,
            "Canonical Windows and Linux CI wheel payloads differ")
    binary = linux / "output/experimental-linux/rentgen-input-core"
    installed = read_json(linux / "output/installed-portable/acceptance.json")
    require(installed.get("version") == version and installed.get("wheel_sha256") == sha(linux_wheel)
            and installed.get("binary_sha256") == sha(binary)
            and installed.get("gui", {}).get("http_rust_import") is True
            and installed["gui"].get("isolated_installed_package") is True,
            "Linux installed receipt differs from collected wheel/binary")
    artifact = records["product"]["artifact"]
    portable = records["portable"]["artifact"]
    inputs = {"schema": 1, "version": version, "rust_component_version": "0.1.0",
              "source_commit": source, "source_tree": tree,
              "windows_kit": {"asset": kit.name, "sha256": kit_hash, "size_bytes": kit.stat().st_size,
                              "ci_run": product_run, "artifact_id": artifact["id"],
                              "artifact_sha256": artifact["digest"].removeprefix("sha256:")},
              "wheel": {"asset": wheel.name, "sha256": sha(wheel), "size_bytes": wheel.stat().st_size},
              "linux_ci": {"ci_run": portable_run, "artifact_id": portable["id"],
                           "artifact_sha256": portable["digest"].removeprefix("sha256:"),
                           "artifact_size_bytes": portable["size_in_bytes"], "python": "3.11"},
              "binary": {"asset": binary.name, "sha256": sha(binary), "size_bytes": binary.stat().st_size}}
    for key, (run_id, workflow, _) in paths.items():
        require(validate_run(api.json(f"/actions/runs/{run_id}"), run_id, source, workflow)
                == records[key]["run"], "CI changed during collection")
    save(output / "inputs.json", inputs)
    candidate = packager().build(output / "inputs.json", wheel, binary, output / "candidate")
    save(output / "collection.json", {"schema": 1, "source_commit": source, "source_tree": tree,
         "runs": records, "canonical_wheel_payload_identical": True,
         "wheel_members_verified": len(canonical_members), "linux_wheel_sha256": sha(linux_wheel),
         "wheel_container_hashes_equal": sha(linux_wheel) == sha(wheel), "sdist_sha256": sha(sdist),
         "candidate": candidate, "release_published": False})


def package_environment(environ):
    return {key: value for key, value in environ.items()
            if not key.upper().startswith(("GH_", "ACTIONS_"))
            and key.upper() not in {"GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME"}}


def run_tool(argv, output, env, timeout=300):
    with output.open("xb") as log:
        child = subprocess.Popen(list(map(str, argv)), cwd=ROOT, env=env,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=15)
            raise ValueError("Candidate qualification deadline exceeded") from None
    require(code == 0, "Candidate qualification failed; raw execution logs are not published")
    require(output.stat().st_size <= 8 * 1024**2, "Candidate execution log exceeds bound")


def qualify(source, output):
    require(sys.platform == "linux" and os.getuid() != 0,
            "Qualification requires a real unprivileged Linux runner")
    require(not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"),
            "Qualification must run in a separate step without GitHub credentials")
    tree = bind_source(source)
    inputs = read_json(output / "inputs.json")
    collection = read_json(output / "collection.json")
    require(inputs["source_commit"] == collection["source_commit"] == source
            and inputs["source_tree"] == collection["source_tree"] == tree,
            "Collected source identity differs")
    helper = packager()
    helper.validate_inputs(inputs)
    candidate = output / "candidate"
    manifest = read_json(candidate / helper.MANIFEST)
    require(manifest["inputs"] == inputs and manifest["sha256"] == collection["candidate"]["sha256"],
            "Candidate differs from collected inputs")
    require(manifest["asset"] == helper.version_name(inputs["version"]) + ".tar.gz"
            and {path.name for path in candidate.iterdir()}
            == {manifest["asset"], helper.MANIFEST, helper.CHECKSUMS}, "Unexpected candidate inventory")
    require((candidate / helper.CHECKSUMS).read_bytes()
            == (manifest["sha256"] + "  " + manifest["asset"] + "\n").encode(),
            "Candidate checksum file differs")
    archive = candidate / manifest["asset"]
    files = helper.verified_payload(helper.read_regular(archive, helper.MAX_TOTAL), manifest)
    _, canonical_manifest = helper.candidate(
        inputs, files[inputs["wheel"]["asset"]], files["bin/rentgen-input-core"]
    )
    require(manifest == canonical_manifest, "Candidate manifest differs from canonical source payload")
    extracted = helper.fresh_directory(output / "extracted")
    for name, raw in sorted(files.items()):
        target = extracted / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        target.chmod(helper.file_mode(name))
    env = package_environment(os.environ)
    wheel, binary = extracted / inputs["wheel"]["asset"], extracted / "bin/rentgen-input-core"
    installed = output / "installed"
    run_tool([sys.executable, ROOT / "scripts/verification/verify_portable_delivery.py",
              "--wheel", wheel, "--binary", binary, "--expected-version", inputs["version"],
              "--output", installed], output / "installed.log", env)
    receipt = read_json(installed / "acceptance.json")
    require(receipt.get("wheel_sha256") == inputs["wheel"]["sha256"]
            and receipt.get("binary_sha256") == inputs["binary"]["sha256"]
            and receipt.get("version") == inputs["version"]
            and receipt.get("gui", {}).get("http_rust_import") is True
            and receipt["gui"].get("isolated_installed_package") is True,
            "Final candidate installed smoke did not bind exact delivered bytes")
    env.update(RENTGEN_GUI_INSTALLED_PYTHON=str(installed / "environment/bin/python"),
               RENTGEN_GUI_EXPECTED_VERSION=inputs["version"],
               RENTGEN_INPUT_CORE_TEST_BINARY=str(binary))
    run_tool(["npm", "--prefix", "tests/gui/browser", "test"], output / "browser.log", env, timeout=900)
    junit = ROOT / "output/gui-browser/junit.xml"
    require(junit.stat().st_size <= MAX_JSON, "Browser receipt exceeds bound")
    cases = ET.parse(junit).findall(".//testcase")
    require(len(cases) == 43 and all(not any(case.find(tag) is not None
            for tag in ("failure", "error", "skipped")) for case in cases),
            "All 43 real browser checks must pass without skips")
    require(sha(archive) == manifest["sha256"] and sha(wheel) == inputs["wheel"]["sha256"]
            and sha(binary) == inputs["binary"]["sha256"], "Candidate bytes changed during qualification")
    require(bind_source(source) == tree, "Source identity changed during qualification")
    receipts = output / "receipts"
    receipts.mkdir()
    save(receipts / "installed.json", receipt)
    (receipts / "browser.xml").write_bytes(junit.read_bytes())
    save(receipts / "qualification.json", {"schema": 1, "candidate_qualification_passed": True,
         "source_commit": source, "source_tree": tree, "version": inputs["version"],
         "archive_sha256": manifest["sha256"], "wheel_sha256": sha(wheel), "binary_sha256": sha(binary),
         "browser_cases": len(cases), "browser_skipped": 0, "sandbox_enabled": True,
         "canonical_windows_wheel": True, "credentials_removed": True,
         "release_published": False, "full_product_ready": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "qualify"))
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product-run", type=int)
    parser.add_argument("--portable-run", type=int)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.mode == "collect":
        if args.product_run is None or args.portable_run is None:
            parser.error("collect requires both exact CI run IDs")
        collect(args.source, args.product_run, args.portable_run, output, GitHub(os.environ.get("GH_TOKEN")))
    else:
        qualify(args.source, output)
    print(json.dumps({"mode": args.mode, "completed": True, "release_published": False}))


if __name__ == "__main__":
    main()
