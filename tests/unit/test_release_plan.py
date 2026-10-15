"""Real local Git/bytes/CLI controls for the candidate-only audit, not product acceptance."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verification/verify_release_plan.py"


@pytest.fixture
def verifier():
    spec = importlib.util.spec_from_file_location("candidate_plan_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.contract.__file__).resolve().is_relative_to(ROOT)
    return module


def git(repo, *args):
    return subprocess.check_output(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                                    "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


def save(path, value):
    path.write_bytes((json.dumps(value, sort_keys=True) + "\n").encode())


@pytest.fixture
def package(tmp_path, verifier):
    base = tmp_path.resolve()
    repo, evidence = base / "repo", base / "evidence"
    repo.mkdir()
    evidence.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Contract fixture")
    (repo / "pyproject.toml").write_text('[project]\nversion = "0.1.0.dev19"\n')
    (repo / "integrations/vscode-rentgen").mkdir(parents=True)
    save(repo / "integrations/vscode-rentgen/package.json", {"version": "0.1.20"})
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Fixture source")
    source, tree = git(repo, "rev-parse", "HEAD"), git(repo, "rev-parse", "HEAD^{tree}")
    (repo / "record.txt").write_text("Record after artifact qualification\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Fixture record")
    record = git(repo, "rev-parse", "HEAD")
    def write_blob(name, raw):
        path = evidence / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    raw = write_blob("raw/fixture.log", b"Fixture execution only; not installed qualification.\n")
    license_file = write_blob("licenses/fixture.txt", b"SPDX-License-Identifier: MIT\n")
    plan = {
        "schema": "rentgen-release-plan/2", "channel": "development",
        "source_commit": source, "source_tree": tree, "record_commit": record,
        "components": {"core": {"version": "0.1.0.dev19", "tag": "core-v0.1.0-dev19"},
                       "companion": {"version": "0.1.20", "tag": "companion-v0.1.20"}},
        "component_pair": {"core": "0.1.0.dev19", "companion": "0.1.20"},
        "assets": [], "dependencies": [{"id": "fixture-runtime", "version": "1.0.0",
            "distribution_sha256": hashlib.sha256(b"fixture runtime").hexdigest(),
            "license": "MIT", "license_file": license_file}],
        "deliveries": [], "requirements": [],
    }
    policy, _ = verifier.contract.load_policy()
    asset_ids = {}
    for target in policy["mandatory_deliveries"]:
        kind = target["asset_kind"]
        if kind not in asset_ids:
            identity = kind
            asset_ids[kind] = identity
            plan["assets"].append({"id": identity, "kind": kind,
                **{k: target[k] for k in ("component", "os", "arch")},
                "blob": write_blob("assets/" + kind + ".bin", ("Fixture " + kind).encode())})
    def receipt(scope, asset_list, deps, origin="fixture", kind="lifecycle-execution"):
        item = {"schema": "rentgen-release-evidence/1", "kind": kind, "origin": origin,
            "source_commit": source, "source_tree": tree, "component_pair": plan["component_pair"],
            "scope": scope, "assets": sorted(asset_list), "dependencies": sorted(deps),
            "result": {"executed": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0},
            "execution": {"command": ["fixture-only", "not-an-actual-installer"], "exit_code": 0},
            "attachments": [raw]}
        name = "receipts/" + str(len(list((evidence / "receipts").glob("*.json"))) if (evidence / "receipts").exists() else 0) + ".json"
        return write_blob(name, (json.dumps(item, sort_keys=True) + "\n").encode())
    for target in policy["mandatory_deliveries"]:
        item = {k: target[k] for k in verifier.contract.TUPLE_KEYS}
        item.update(asset=asset_ids[target["asset_kind"]], dependencies=["fixture-runtime"], cells={})
        key = verifier.contract.tuple_key(item)
        for lifecycle in verifier.contract.LIFECYCLE:
            item["cells"][lifecycle] = {"status": "passed", "receipt": receipt(
                {"delivery": key, "lifecycle": lifecycle}, [item["asset"]], item["dependencies"])}
        plan["deliveries"].append(item)
    plan_path = base / "plan.json"
    save(plan_path, plan)
    return {"repo": repo, "root": evidence, "plan": plan, "path": plan_path,
            "receipt": receipt, "blob": write_blob, "policy": policy}


def audit(verifier, package):
    save(package["path"], package["plan"])
    return verifier.check(package["path"], package["root"], package["repo"])


def rewrite_receipt(package, ref, mutate):
    path = package["root"] / ref["path"]
    value = json.loads(path.read_bytes())
    mutate(value)
    save(path, value)
    ref.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size)


def first_cell(package):
    return package["plan"]["deliveries"][0]["cells"]["dependencies"]


def test_valid_parse_is_not_full_qualification_or_publication(verifier, package):
    result = audit(verifier, package)
    assert result["contract_valid"] is True
    assert result["delivery"]["declared_passed"] == 35
    assert result["coverage_complete"] is result["stable_eligible"] is result["published"] is False
    assert len(result["missing"]) == 127
    assert len([x for x in result["unqualified"] if x["cell"].startswith("final-target/")]) == 6
    assert any(x["cell"] == "final-target/macos/ide-client" for x in result["unqualified"])


def test_full_positive_fixture_only_tests_coverage_algorithm(verifier, package):
    plan = package["plan"]
    for identity in package["policy"]["requirements"]:
        plan["requirements"].append({"id": identity, "status": "passed", "receipt": package["receipt"](
            {"requirement": identity, "scope": "full-criterion"},
            [a["id"] for a in plan["assets"]], [d["id"] for d in plan["dependencies"]],
            kind="full-product-criterion")})
    result = audit(verifier, package)
    assert not result["missing"] and not result["failed"]
    assert len(result["unqualified"]) == 35 + 127 + 6
    assert result["origins"] == ["fixture"]
    assert result["qualification_receipt"] is result["coverage_complete"] is result["stable_eligible"] is False


def test_execution_lifecycle_claims_are_bound_but_not_product_authority(verifier, package):
    for delivery in package["plan"]["deliveries"]:
        for cell in delivery["cells"].values():
            rewrite_receipt(package, cell["receipt"], lambda item: item.update(origin="execution"))
    result = audit(verifier, package)
    assert result["delivery"]["coverage_complete"] is True
    assert result["coverage_complete"] is result["stable_eligible"] is False


@pytest.mark.parametrize("change", ["head", "tree", "pair", "record-before-source"])
def test_real_git_binding_does_not_admit_different_source_or_record(verifier, package, change):
    plan = package["plan"]
    if change == "head":
        plan["source_commit"] = plan["record_commit"]
    elif change == "tree":
        plan["source_tree"] = "a" * 40
    elif change == "pair":
        plan["component_pair"]["core"] = "0.1.0.dev20"
    else:
        plan["source_commit"], plan["record_commit"] = plan["record_commit"], plan["source_commit"]
        plan["source_tree"] = git(package["repo"], "rev-parse", plan["source_commit"] + "^{tree}")
    with pytest.raises(ValueError):
        audit(verifier, package)


@pytest.mark.parametrize("channel", ["unknown", "stable", "release-candidate"])
def test_explicit_channel_cannot_relabel_development_versions(verifier, package, channel):
    package["plan"]["channel"] = channel
    with pytest.raises(ValueError):
        audit(verifier, package)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(source_commit="0" * 40),
    lambda x: x.update(source_tree="0" * 40),
    lambda x: x.update(component_pair={"core": "0.0.0", "companion": "0.1.20"}),
    lambda x: x["scope"].update(lifecycle="uninstall"),
    lambda x: x.update(assets=[]),
    lambda x: x.update(dependencies=[]),
    lambda x: x.update(accepted=True),
    lambda x: x["result"].update(executed=True),
])
def test_byte_rebound_receipt_still_requires_correct_typed_scope(verifier, package, mutation):
    rewrite_receipt(package, first_cell(package)["receipt"], mutation)
    with pytest.raises(ValueError):
        audit(verifier, package)


@pytest.mark.parametrize("control", ["failed", "skipped", "no-tests", "nonzero-exit"])
def test_negative_experiment_has_an_actionable_failed_cell(verifier, package, control):
    def mutate(item):
        if control == "failed":
            item["result"].update(passed=0, failed=1)
        elif control == "skipped":
            item["result"].update(passed=0, skipped=1)
        elif control == "no-tests":
            item["result"].update(passed=0, executed=0)
        else:
            item["execution"]["exit_code"] = 1
    rewrite_receipt(package, first_cell(package)["receipt"], mutate)
    result = audit(verifier, package)
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "failed-or-skipped-lifecycle"
    assert not result["stable_eligible"]


def test_omitted_linux_and_one_cell_are_visible_missing_coverage(verifier, package):
    plan = package["plan"]
    # Remove corresponding unused receipt files; the inventory remains exact.
    removed = [d for d in plan["deliveries"] if d["os"] == "linux"]
    plan["deliveries"] = [d for d in plan["deliveries"] if d["os"] != "linux"]
    for delivery in removed:
        for cell in delivery["cells"].values():
            (package["root"] / cell["receipt"]["path"]).unlink()
    cell = plan["deliveries"][0]["cells"].pop("cancel")
    (package["root"] / cell["receipt"]["path"]).unlink()
    result = audit(verifier, package)
    cells = [x["cell"] for x in result["missing"]]
    assert sum("/linux/" in x for x in cells) == 14
    assert any(x.endswith("/cancel") for x in cells)


@pytest.mark.parametrize("control", ["duplicate", "unknown-tuple", "unknown-cell", "na"])
def test_author_cannot_change_closed_policy(verifier, package, control):
    delivery = package["plan"]["deliveries"][0]
    if control == "duplicate":
        package["plan"]["deliveries"].append(copy.deepcopy(delivery))
    elif control == "unknown-tuple":
        delivery["os"] = "any-platform"
    elif control == "unknown-cell":
        delivery["cells"]["anything"] = {"status": "missing", "receipt": None}
    else:
        delivery["cells"]["cancel"] = {"status": "not-applicable", "receipt": None}
    with pytest.raises(ValueError):
        audit(verifier, package)


@pytest.mark.parametrize("control", ["same-size-asset", "receipt-digest", "extra-file", "missing-file", "extra-asset"])
def test_real_file_inventory_and_hash_tampering_are_refused(verifier, package, control):
    asset = package["plan"]["assets"][0]
    if control == "same-size-asset":
        path = package["root"] / asset["blob"]["path"]
        path.write_bytes(b"x" * path.stat().st_size)
    elif control == "receipt-digest":
        first_cell(package)["receipt"]["sha256"] = "0" * 64
    elif control == "extra-file":
        (package["root"] / "undeclared.txt").write_bytes(b"extra")
    elif control == "missing-file":
        (package["root"] / asset["blob"]["path"]).unlink()
    else:
        extra = copy.deepcopy(asset)
        extra["id"] = "extra"
        package["plan"]["assets"].append(extra)
    with pytest.raises((ValueError, OSError)):
        audit(verifier, package)


@pytest.mark.parametrize("name", ["../escape", "a/../../escape", "C:/escape", "a\\b", "/absolute", "a/./b"])
def test_traversal_and_platform_path_aliases_are_refused(verifier, name):
    with pytest.raises(ValueError):
        verifier.contract.relative(name)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
                                  b'[' * 26 + b'0' + b']' * 26, b'{"x":"' + b'a' * 4097 + b'"}'],
                         ids=("duplicate", "nan", "infinity", "float-overflow", "depth", "string"))
def test_duplicate_nonfinite_and_unbounded_json_are_refused(verifier, raw):
    with pytest.raises(ValueError):
        verifier.contract.strict_json(raw)


def test_symlink_file_and_ancestor_are_not_followed(verifier, package):
    if os.name == "nt":
        pytest.skip("Symlink creation needs Windows privilege; reparse flag is checked by contract")
    root = package["root"]
    link = root.parent / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        verifier.contract.checked_bytes(link / "raw/fixture.log")
    (root / "extra-link").symlink_to(root / "raw/fixture.log")
    with pytest.raises(ValueError, match="Symlink"):
        audit(verifier, package)


def test_requirement_catalog_cannot_drop_a_real_id_and_silently_change_goal(verifier, tmp_path, monkeypatch):
    fake = tmp_path.resolve()
    (fake / "scripts/release").mkdir(parents=True)
    (fake / "docs/product").mkdir(parents=True)
    original = json.loads((ROOT / "scripts/release/release_policy.json").read_bytes())
    original["requirements"].remove("DAILY-NATIVE-01")
    original["requirements"].append("INVENTED-GATE-01")
    save(fake / "scripts/release/release_policy.json", original)
    (fake / "docs/product/FULL-FINAL-PLAN.md").write_bytes(
        (ROOT / "docs/product/FULL-FINAL-PLAN.md").read_bytes().replace(b"DAILY-NATIVE-01", b"INVENTED-GATE-01"))
    monkeypatch.setattr(verifier.contract, "ROOT", fake)
    with pytest.raises(ValueError, match="catalog"):
        verifier.contract.load_policy()


def ci_claim(package, identity):
    plan = package["plan"]
    ref = package["receipt"]({"requirement": identity, "scope": "full-criterion"},
                             [a["id"] for a in plan["assets"]],
                             [d["id"] for d in plan["dependencies"]],
                             origin="execution", kind="github-main-ci")
    artifact = package["blob"]("ci/artifact.zip", b"Exact fixture artifact wrapper bytes")
    def mutate(item):
        item["execution"] = {"repository": "DmitrL-dev/1cai-public",
            "workflow": ".github/workflows/core-ci.yml", "run_id": 37, "run_attempt": 2,
            "artifact_id": 95, "event": "push", "branch": "main", "status": "completed",
            "conclusion": "success", "artifact": artifact}
    rewrite_receipt(package, ref, mutate)
    plan["requirements"].append({"id": identity, "status": "passed", "receipt": ref})
    return ref


@pytest.mark.parametrize("identity", ["DAILY-NATIVE-01", "IDE-AI-01", "IDE-SC-23", "FINAL-STABLE-CHANNEL-01"])
def test_successful_ci_is_not_native_model_human_or_product_experience(verifier, package, identity):
    ci_claim(package, identity)
    result = audit(verifier, package)
    cell = next(x for x in result["unqualified"] if x["cell"] == identity)
    assert cell["reason"] == "wrong-experience-kind-for-full-criterion"
    assert not result["stable_eligible"]


@pytest.mark.parametrize("field,value", [("event", "pull_request"), ("branch", "feature"),
    ("run_attempt", True), ("artifact_id", 0), ("workflow", ".github/workflows/unknown.yml")])
def test_wrong_ci_event_attempt_and_artifact_binding_are_refused(verifier, package, field, value):
    ref = ci_claim(package, "DAILY-NATIVE-01")
    rewrite_receipt(package, ref, lambda item: item["execution"].update({field: value}))
    with pytest.raises(ValueError):
        audit(verifier, package)


def test_inherited_git_repository_environment_cannot_substitute_source(verifier, package, monkeypatch):
    monkeypatch.setenv("GIT_DIR", str(package["repo"] / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(package["repo"]))
    unrelated = package["repo"].parent / "not-a-repository"
    unrelated.mkdir()
    with pytest.raises(ValueError, match="Git source"):
        verifier.contract.bind_git(package["plan"], unrelated)
    assert audit(verifier, package)["contract_valid"]


def test_missing_cell_is_visible_without_fabricated_receipt(verifier, package):
    cell = first_cell(package)
    (package["root"] / cell["receipt"]["path"]).unlink()
    cell.update(status="missing", receipt=None)
    result = audit(verifier, package)
    assert any(x["reason"] == "missing-lifecycle-evidence" for x in result["missing"])


def test_deep_committed_toml_source_returns_closed_cli_json(verifier, package):
    repo = package["repo"]
    (repo / "pyproject.toml").write_text("[project]\nversion = " + "[" * 600 + "0" + "]" * 600)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Malformed source control")
    package["plan"].update(source_commit=git(repo, "rev-parse", "HEAD"),
                           source_tree=git(repo, "rev-parse", "HEAD^{tree}"),
                           record_commit=git(repo, "rev-parse", "HEAD"))
    save(package["path"], package["plan"])
    result = subprocess.run([sys.executable, str(SCRIPT), "check", "--plan", str(package["path"]),
        "--evidence-root", str(package["root"]), "--repository", str(repo)], capture_output=True)
    assert result.returncode == 1 and not result.stderr
    assert json.loads(result.stdout)["reason"] == "Invalid bounded source component metadata"


def test_cli_is_deterministic_read_only_and_does_not_create_receipts(verifier, package):
    def inventory():
        return {str(p.relative_to(package["root"].parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in package["root"].parent.rglob("*") if p.is_file()}
    before = inventory()
    command = [sys.executable, str(SCRIPT), "check", "--plan", str(package["path"]),
               "--evidence-root", str(package["root"]), "--repository", str(package["repo"])]
    first = subprocess.run(command, capture_output=True)
    second = subprocess.run(command, capture_output=True)
    assert first.returncode == second.returncode == 2
    assert first.stdout == second.stdout and not first.stderr and not second.stderr
    assert json.loads(first.stdout)["published"] is False
    assert inventory() == before
    assert git(package["repo"], "status", "--porcelain") == ""
    package["path"].write_bytes(b'{"schema":"one","schema":"two"}')
    invalid = subprocess.run(command, capture_output=True)
    assert invalid.returncode == 1 and json.loads(invalid.stdout)["contract_valid"] is False
    assert not invalid.stderr
