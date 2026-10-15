"""Release candidates bind successful Actions runs and bytes to accepted source."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request
from zipfile import ZipFile, ZipInfo

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 40
OTHER_SOURCE = "b" * 40
REPOSITORY = "DmitrL-dev/1cai-public"
WORKFLOW = ".github/workflows/core-ci.yml"
RUN_ID = 123456
ARTIFACT_NAME = "verified-core-development"


@pytest.fixture
def candidate(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/verification"))
    spec = importlib.util.spec_from_file_location(
        "verify_release_candidate_contract",
        ROOT / "scripts/verification/verify_release_candidate.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def successful_run():
    return {
        "id": RUN_ID,
        "head_sha": SOURCE,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "path": WORKFLOW,
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
        "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{RUN_ID}",
        "run_attempt": 1,
        "updated_at": "2026-10-15T00:00:00Z",
    }


def artifact(payload=b"trusted candidate bytes"):
    return {
        "id": 789012,
        "name": ARTIFACT_NAME,
        "expired": False,
        "size_in_bytes": len(payload),
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "workflow_run": {"id": RUN_ID, "head_sha": SOURCE},
    }


def artifact_listing(items):
    return {"total_count": len(items), "artifacts": items}


def test_successful_main_push_is_accepted(candidate):
    candidate.validate_run(successful_run(), RUN_ID, SOURCE, WORKFLOW)


@pytest.mark.parametrize("field,value", [
    ("id", RUN_ID + 1),
    ("head_sha", OTHER_SOURCE),
    ("head_branch", "codex/unaccepted-candidate"),
    ("event", "pull_request"),
    ("event", "workflow_dispatch"),
    ("status", "in_progress"),
    ("conclusion", "failure"),
    ("conclusion", "cancelled"),
    ("conclusion", None),
    ("path", ".github/workflows/unrelated.yml"),
    ("repository", {"full_name": "other-owner/1cai-public"}),
    ("head_repository", {"full_name": "other-owner/1cai-public"}),
])
def test_other_or_unsuccessful_run_cannot_supply_release_bytes(candidate, field, value):
    run = successful_run()
    run[field] = value
    with pytest.raises(ValueError):
        candidate.validate_run(run, RUN_ID, SOURCE, WORKFLOW)


def test_artifact_is_selected_by_exact_name(candidate):
    wanted = artifact()
    unrelated = {**wanted, "id": 789013, "name": "other-evidence"}
    selected = candidate.select_artifact(
        artifact_listing([unrelated, wanted]), ARTIFACT_NAME, RUN_ID, SOURCE
    )
    assert selected["id"] == wanted["id"]
    assert selected["digest"] == wanted["digest"]


@pytest.mark.parametrize("artifacts", [[], [artifact(), artifact()]])
def test_missing_or_ambiguous_artifact_is_rejected(candidate, artifacts):
    with pytest.raises(ValueError):
        candidate.select_artifact(artifact_listing(artifacts), ARTIFACT_NAME, RUN_ID, SOURCE)


def test_partial_artifact_listing_is_not_accepted(candidate):
    with pytest.raises(ValueError):
        candidate.select_artifact(
            {"total_count": 101, "artifacts": [artifact()]}, ARTIFACT_NAME, RUN_ID, SOURCE
        )


@pytest.mark.parametrize("field,value", [
    ("expired", True),
    ("size_in_bytes", 0),
    ("size_in_bytes", -1),
    ("size_in_bytes", 128 * 1024**2 + 1),
    ("size_in_bytes", True),
    ("size_in_bytes", 1.5),
    ("digest", None),
    ("digest", "sha256:" + "z" * 64),
    ("digest", "sha256:" + "a" * 63),
    ("digest", "sha1:" + "a" * 40),
    ("workflow_run", {"id": RUN_ID + 1, "head_sha": SOURCE}),
    ("workflow_run", {"id": RUN_ID, "head_sha": OTHER_SOURCE}),
])
def test_untrusted_artifact_metadata_is_rejected(candidate, field, value):
    item = artifact()
    item[field] = value
    with pytest.raises(ValueError):
        candidate.select_artifact(artifact_listing([item]), ARTIFACT_NAME, RUN_ID, SOURCE)


def test_download_checks_real_bytes_without_executing_archive(candidate, tmp_path):
    archive = tmp_path / "candidate.zip"
    marker = tmp_path / "executed"
    with ZipFile(archive, "w") as package:
        package.writestr("setup.py", f"open({str(marker)!r}, 'w').write('executed')")
    metadata = artifact(archive.read_bytes())
    candidate.verify_download(archive, metadata)
    assert not marker.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["candidate.zip"]


@pytest.mark.parametrize("tampering", ["size", "digest"])
def test_download_refuses_size_or_same_size_hash_mismatch(candidate, tmp_path, tampering):
    payload = b"trusted candidate bytes"
    archive = tmp_path / "candidate.zip"
    archive.write_bytes(payload + b"!" if tampering == "size" else b"x" * len(payload))
    with pytest.raises(ValueError):
        candidate.verify_download(archive, artifact(payload))


def test_package_processes_receive_no_actions_credentials_or_python_injection(candidate):
    environment = {
        "PATH": "/trusted/runtime",
        "USERPROFILE": "/isolated/profile",
        "GH_TOKEN": "do-not-pass",
        "GH_ENTERPRISE_TOKEN": "do-not-pass",
        "gh_custom_token": "do-not-pass",
        "GITHUB_TOKEN": "do-not-pass",
        "github_token": "do-not-pass",
        "ACTIONS_RUNTIME_TOKEN": "do-not-pass",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "do-not-pass",
        "ACTIONS_CACHE_URL": "do-not-pass",
        "PYTHONPATH": "/untrusted/module",
        "PYTHONHOME": "/untrusted/runtime",
    }
    original = copy.deepcopy(environment)
    cleaned = candidate.package_environment(environment)
    assert environment == original
    assert cleaned["PATH"] == environment["PATH"]
    assert cleaned["USERPROFILE"] == environment["USERPROFILE"]
    assert not any(
        key.upper().startswith(("GH_", "ACTIONS_"))
        or key.upper() in {"GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME"}
        for key in cleaned
    )
    assert "do-not-pass" not in cleaned.values()


@pytest.mark.parametrize("unredirected", [False, True])
def test_https_artifact_redirect_never_forwards_authorization(candidate, unredirected):
    request = Request("https://api.github.com/repos/owner/project/actions/artifacts/1/zip")
    if unredirected:
        request.add_unredirected_header("Authorization", "Bearer credential-fixture")
    else:
        request.add_header("Authorization", "Bearer credential-fixture")
    request.add_header("Accept", "application/vnd.github+json")
    redirected = candidate.NoAuthRedirect().redirect_request(
        request, None, 302, "Found", {}, "https://artifact.example.invalid/candidate.zip"
    )
    assert redirected.full_url == "https://artifact.example.invalid/candidate.zip"
    assert all(key.lower() != "authorization" for key, _ in redirected.header_items())


@pytest.mark.parametrize("url", [
    "http://artifact.example.invalid/candidate.zip",
    "file:///tmp/candidate.zip",
    "ftp://artifact.example.invalid/candidate.zip",
])
def test_artifact_redirect_refuses_non_https_transport(candidate, url):
    request = Request("https://api.github.com/repos/owner/project/actions/artifacts/1/zip")
    request.add_header("Authorization", "Bearer credential-fixture")
    with pytest.raises((ValueError, HTTPError)):
        candidate.NoAuthRedirect().redirect_request(request, None, 302, "Found", {}, url)


@pytest.fixture
def source_repository(tmp_path, monkeypatch, candidate):
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=checkout, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Release candidate contract fixture")
    git("config", "user.email", "test@example.invalid")
    git("config", "core.autocrlf", "false")
    source_file = checkout / "source.txt"
    source_file.write_text("accepted candidate\n", encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        '[project]\nversion = "0.1.0.dev18"\n', encoding="utf-8"
    )
    git("add", ".")
    git("commit", "-qm", "Accepted source fixture")
    source = git("rev-parse", "HEAD")
    git("branch", "-M", "main")
    git("update-ref", "refs/remotes/origin/main", source)
    monkeypatch.setattr(candidate, "ROOT", checkout)
    return candidate, git, source_file, source


def test_checkout_binds_exact_source_on_accepted_main(source_repository):
    module, _, _, source = source_repository
    module.bind_source(source)


def test_different_checkout_head_is_rejected(source_repository):
    module, _, _, _ = source_repository
    with pytest.raises(ValueError):
        module.bind_source(OTHER_SOURCE)


def test_unaccepted_branch_commit_is_rejected(source_repository):
    module, git, source_file, _ = source_repository
    git("checkout", "-qb", "unaccepted")
    source_file.write_text("unaccepted candidate\n", encoding="utf-8")
    git("commit", "-qam", "Unaccepted source fixture")
    with pytest.raises(ValueError):
        module.bind_source(git("rev-parse", "HEAD"))


def test_accepted_source_can_precede_fetched_main(source_repository):
    module, git, source_file, source = source_repository
    source_file.write_text("later accepted main\n", encoding="utf-8")
    git("commit", "-qam", "Later accepted main fixture")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    git("checkout", "-q", "--detach", source)
    module.bind_source(source)


@pytest.mark.parametrize("name", ["../escaped", "/absolute", "nested\\escaped", "CON", "a/../escaped"])
def test_collector_uses_safe_archive_paths(candidate, tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as package:
        package.writestr(name, "untrusted payload")
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError):
        candidate.extract(archive, destination)
    assert not list(destination.rglob("*"))
    assert not (tmp_path / "escaped").exists()


def test_collector_rechecks_download_digest_before_extraction(source_repository, tmp_path, monkeypatch):
    module, _, _, source = source_repository
    archive = tmp_path / "api-wrapper.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("setup.py", "raise RuntimeError('must not execute')")
    trusted = archive.read_bytes()
    item = artifact(trusted)
    item["workflow_run"]["head_sha"] = source
    run = successful_run()
    run["head_sha"] = source
    extracted = []

    def forbidden_extract(*args):
        extracted.append(args)
        raise AssertionError("An unverified download reached extraction")

    class ChangedDownload:
        def json(self, path):
            if path == f"/actions/runs/{RUN_ID}":
                return run
            if path == f"/actions/runs/{RUN_ID}/artifacts?per_page=100":
                return artifact_listing([item])
            raise AssertionError(f"Unexpected API request: {path}")

        def download(self, metadata, destination):
            # Preserve the wrapper length so only the independent digest guard
            # can catch a downloader that did not validate its own response.
            destination.write_bytes(trusted[:-1] + bytes([trusted[-1] ^ 1]))

    monkeypatch.setattr(module, "extract", forbidden_extract)
    output = tmp_path / "collected"
    with pytest.raises(ValueError, match="API size/digest"):
        module.collect(source, RUN_ID, RUN_ID + 1, output, ChangedDownload())
    assert extracted == []
    assert not (output / "collection.json").exists()
    assert not (output / "candidate").exists()


@pytest.mark.parametrize("wheel_variant", ["identical", "different-container", "changed-member"])
def test_collect_binds_nested_ci_bytes_and_builds_only_a_candidate(
    source_repository, tmp_path, monkeypatch, wheel_variant
):
    module, git, _, _ = source_repository
    spec = importlib.util.spec_from_file_location(
        "candidate_real_supplement_packager", ROOT / "scripts/release/prepare_experimental_linux.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    monkeypatch.setattr(helper, "ROOT", module.ROOT)
    monkeypatch.setattr(module, "packager", lambda: helper)
    files = {name: b"Synthetic source notice fixture\n" for name in helper.SOURCE_PATHS[:-1]}
    files.update({
        "rust/input-core/licenses/SHA256SUMS": b"Synthetic license inventory fixture\n",
        "rust/input-core/licenses/example/LICENSE": b"Synthetic original license fixture\n",
        "rust/input-core/Cargo.toml": b'[package]\nversion = "0.1.0"\n',
    })
    for name, raw in files.items():
        path = module.ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    git("add", ".")
    git("commit", "-qm", "Bind synthetic packaging notices")
    source = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    git("update-ref", "refs/remotes/origin/main", source)
    version = "0.1.0.dev18"

    def zipped(contents, timestamp=(2020, 1, 1, 0, 0, 0)):
        output = io.BytesIO()
        with ZipFile(output, "w") as archive:
            for name, raw in contents.items():
                archive.writestr(ZipInfo(name, date_time=timestamp), raw)
        return output.getvalue()

    def digest(raw):
        return hashlib.sha256(raw).hexdigest()

    def json_bytes(value):
        return json.dumps(value).encode()

    wheel_name = f"rentgen_core-{version}-py3-none-any.whl"
    wheel_files = {
        f"rentgen_core-{version}.dist-info/METADATA": f"Name: rentgen-core\nVersion: {version}\n",
        "rentgen_core/__init__.py": "raise RuntimeError('fixture must never execute')\n",
    }
    wheel = zipped(wheel_files)
    linux_wheel = wheel
    if wheel_variant == "different-container":
        linux_wheel = zipped(wheel_files, timestamp=(2021, 2, 3, 4, 5, 6))
        assert linux_wheel != wheel
    elif wheel_variant == "changed-member":
        linux_wheel = zipped({**wheel_files, "rentgen_core/__init__.py": "raise RuntimeError('different member')\n"})
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    header[16:20] = b"\x03\x00\x3e\x00"
    binary = bytes(header)
    sdist = b"Synthetic sdist bytes; never installed or executed\n"
    kit_name = f"rentgen-core-{version}-windows-py311.zip"
    kit_prefix = kit_name[:-4] + "/"
    kit_files = {
        wheel_name: wheel,
        f"rentgen_core-{version}.tar.gz": sdist,
        "bsl-scan.exe": b"Synthetic Windows scanner; never executed\n",
        "build-input-hashes.json": json_bytes({"source_commit": source}),
    }
    inventory = {
        "version": version,
        "files": {name: {"sha256": digest(raw), "size_bytes": len(raw)}
                  for name, raw in kit_files.items()},
    }
    kit = zipped({
        **{kit_prefix + name: raw for name, raw in kit_files.items()},
        kit_prefix + "SHA256SUMS.json": json_bytes(inventory),
    })
    windows_receipt = {
        "source_commit": source,
        "builds_identical": True,
        "offline_install": {"accepted": True, "archive_sha256": digest(kit)},
        "kit": {"archive_sha256": digest(kit), "wheel_sha256": digest(wheel),
                "sdist_sha256": digest(sdist)},
    }
    product_wrapper = zipped({
        "core-kit/" + kit_name: kit,
        "core-kit/acceptance.json": json_bytes(windows_receipt),
    })
    portable_wrapper = zipped({
        "dist/" + wheel_name: linux_wheel,
        "output/experimental-linux/rentgen-input-core": binary,
        "output/installed-portable/acceptance.json": json_bytes({
            "version": version,
            "wheel_sha256": digest(linux_wheel),
            "binary_sha256": digest(binary),
            "gui": {"http_rust_import": True, "isolated_installed_package": True},
        }),
    })
    snapshots, listings, downloads = {}, {}, {}
    for offset, (wrapper, workflow, name) in enumerate((
        (product_wrapper, WORKFLOW, ARTIFACT_NAME),
        (portable_wrapper, ".github/workflows/portable-ci.yml", "experimental-linux-python-3.11"),
    )):
        run_id = RUN_ID + offset
        run = {**successful_run(), "id": run_id, "head_sha": source, "path": workflow}
        item = {**artifact(wrapper), "id": 789012 + offset, "name": name,
                "workflow_run": {"id": run_id, "head_sha": source}}
        snapshots[f"/actions/runs/{run_id}"] = run
        listings[f"/actions/runs/{run_id}/artifacts?per_page=100"] = artifact_listing([item])
        downloads[item["id"]] = wrapper

    class SyntheticCI:
        def json(self, path):
            return copy.deepcopy({**snapshots, **listings}[path])

        def download(self, metadata, destination):
            destination.write_bytes(downloads[metadata["id"]])

    def no_package_execution(*args, **kwargs):
        raise AssertionError("Collection must not execute package inputs")

    monkeypatch.setattr(module, "run_tool", no_package_execution)
    output = tmp_path / "collected"
    if wheel_variant == "changed-member":
        with pytest.raises(ValueError, match="[Ww]heel.*differ"):
            module.collect(source, RUN_ID, RUN_ID + 1, output, SyntheticCI())
        assert not (output / "candidate").exists()
        assert not (output / "collection.json").exists()
        return

    module.collect(source, RUN_ID, RUN_ID + 1, output, SyntheticCI())
    inputs = json.loads((output / "inputs.json").read_text("utf-8"))
    collection = json.loads((output / "collection.json").read_text("utf-8"))
    manifest = json.loads((output / "candidate" / helper.MANIFEST).read_text("utf-8"))
    assert inputs["source_commit"] == collection["source_commit"] == source
    assert inputs["source_tree"] == collection["source_tree"] == tree
    assert inputs["wheel"] == {"asset": wheel_name, "sha256": digest(wheel), "size_bytes": len(wheel)}
    assert inputs["windows_kit"]["sha256"] == digest(kit)
    assert inputs["windows_kit"]["artifact_sha256"] == digest(product_wrapper)
    assert inputs["linux_ci"]["artifact_sha256"] == digest(portable_wrapper)
    assert inputs["binary"]["sha256"] == digest(binary)
    assert collection["canonical_wheel_payload_identical"] is True
    assert collection["wheel_container_hashes_equal"] is (wheel_variant == "identical")
    assert collection["wheel_members_verified"] == len(wheel_files)
    assert collection["linux_wheel_sha256"] == digest(linux_wheel)
    assert collection["release_published"] is False
    assert collection["candidate"]["accepted"] is False
    assert collection["candidate"]["candidate"] is True
    assert manifest["inputs"] == inputs
    archive = output / "candidate" / manifest["asset"]
    assert digest(archive.read_bytes()) == manifest["sha256"]
    payload = helper.verified_payload(archive.read_bytes(), manifest)
    assert payload[wheel_name] == wheel
    assert payload["bin/rentgen-input-core"] == binary
    assert payload["LICENSE"] == files["LICENSE"]
    assert payload["rust/input-core/licenses/example/LICENSE"] == files["rust/input-core/licenses/example/LICENSE"]
    assert not (output / "receipts").exists()


def test_candidate_workflow_uses_read_only_authority_and_exact_source():
    text = (ROOT / ".github/workflows/release-candidate-ci.yml").read_text("utf-8")
    workflow = yaml.safe_load(text)
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    for job in workflow["jobs"].values():
        assert all(value != "write" for value in job.get("permissions", {}).values())
        checkout = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
        assert len(checkout) == 1
        assert checkout[0]["with"] == {
            "ref": "${{ inputs.source_sha }}",
            "fetch-depth": 0,
            "persist-credentials": False,
        }
        assert "GH_TOKEN" not in job.get("env", {})
        assert "GITHUB_TOKEN" not in job.get("env", {})
        token_steps = [step for step in job["steps"] if "GH_TOKEN" in step.get("env", {})]
        assert len(token_steps) == 1
        assert "verify_release_candidate.py collect " in token_steps[0]["run"]
        assert " qualify " not in token_steps[0]["run"]
        assert token_steps[0]["env"] == {"GH_TOKEN": "${{ github.token }}"}
        for step in job["steps"]:
            if "qualify --source" in step.get("run", ""):
                assert not step.get("env", {}).get("GH_TOKEN")
                assert not step.get("env", {}).get("GITHUB_TOKEN")
            assert "${{ inputs." not in step.get("run", "")
    for forbidden in ("gh release", "gh pr merge", "git push", "git tag", "sudo "):
        assert forbidden not in text
