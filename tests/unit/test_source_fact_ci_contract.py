"""Static, platform-neutral CI wiring checks; never launch qualification."""
import ast
from pathlib import Path
import shlex

import yaml

ROOT = Path(__file__).resolve().parents[2]
SUPERVISED = [
    "tests/unit/test_source_fact_runtime_boundaries.py",
    "tests/unit/test_source_fact_lifecycle_completion.py",
    "tests/unit/test_source_fact_wire_receipt_gaps.py",
]


def workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text("utf-8"))


def test_linux_diagnostic_excludes_only_the_three_supervised_modules():
    job = workflow("portable-ci.yml")["jobs"]["linux"]
    step = next(s for s in job["steps"] if s.get("name") ==
                "Diagnostic full Linux suite with known Windows baseline")
    lines = [line.strip() for line in step["run"].splitlines()]
    commands = [line for line in lines if line.startswith("python -m pytest")]
    assert len(commands) == 1
    args = shlex.split(commands[0])
    ignored = [arg.removeprefix("--ignore=") for arg in args if arg.startswith("--ignore=")]
    assert len(ignored) == 3 and set(ignored) == set(SUPERVISED)
    assert [arg for arg in args if not arg.startswith("--ignore=")] == [
        "python", "-m", "pytest", "-q", "--tb=short",
        "--junitxml=output/linux-diagnostic.xml", ">", "output/linux-diagnostic.log", "2>&1",
    ]
    assert lines[lines.index(commands[0]) + 1:lines.index(commands[0]) + 3] == ["status=$?", "set -e"]
    assert lines[-1] == (
        "python scripts/verification/check_linux_baseline.py --junit output/linux-diagnostic.xml "
        "--baseline docs/product/evidence/linux-baseline-classification-20261005.json "
        '--pytest-exit "$status" --output output/linux-baseline-comparison.json'
    )


def test_ordinary_and_special_workflows_have_distinct_truthful_contracts():
    for name, label, step_name, output, flag in [
        ("source-facts-ci.yml", "Linux source facts (174 ordinary + installed wheel)",
         "Required supervised 174 ordinary variants", "ordinary174", ["--ordinary-only"]),
        ("source-facts-qualification.yml", "Special qualification (176 + installed wheel)",
         "Required default supervised 176-variant qualification", "full176", []),
    ]:
        doc = workflow(name)
        # PyYAML's YAML 1.1 loader maps the GitHub Actions key `on` to True.
        events = doc.get("on", doc.get(True))
        assert set(events) == ({"push", "pull_request"} if flag else {"workflow_dispatch"})
        job = doc["jobs"]["linux-source-facts"]
        assert job["name"] == label
        assert job["runs-on"] == "ubuntu-24.04"
        assert job["defaults"]["run"]["shell"] == "bash"
        assert "if" not in job and "continue-on-error" not in job
        assert all("continue-on-error" not in step for step in job["steps"])
        full = next(s for s in job["steps"] if s.get("name") == step_name)
        smoke = next(s for s in job["steps"] if s.get("name") == "Required installed-wheel source-fact smoke")
        assert "if" not in full and "if" not in smoke
        assert job["steps"].index(full) < job["steps"].index(smoke)
        assert shlex.split(full["run"]) == [
            "$BUILD_ROOT/tools/bin/python", "-I", "-B",
            "$SOURCE_ROOT/tests/fixtures/source_facts/boundary_supervisor.py",
            "--root", "$SOURCE_ROOT", "--pins", "$EVIDENCE/pins.json",
            "--pins-sha256", "$(cat $EVIDENCE/pins.sha256)",
            "--output", "$EVIDENCE/" + output, *flag,
        ]
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        assert "--polling-correction-only" not in runs
        assert "trace_launcher" not in runs
        assert "setcap " not in runs and "ptrace_scope" not in runs and "sudoers" not in runs


def test_default_supervisor_owns_all_three_modules_and_176_denominator():
    # Parse source rather than importing the Linux process/ptrace harness.
    tree = ast.parse((ROOT / "tests/fixtures/source_facts/boundary_supervisor.py").read_text("utf-8"))
    qualify = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "qualify")
    defaults = dict(zip((arg.arg for arg in qualify.args.kwonlyargs), qualify.args.kw_defaults))
    assert ast.literal_eval(defaults["polling_correction_only"]) is False
    assignments = {target.id: node.value for node in ast.walk(qualify) if isinstance(node, ast.Assign)
                   for target in node.targets if isinstance(target, ast.Name)}
    paths = assignments["test_paths"]
    assert isinstance(paths, ast.IfExp) and isinstance(paths.test, ast.Name)
    assert paths.test.id == "polling_correction_only"
    assert ast.literal_eval(paths.orelse) == SUPERVISED
    count = assignments["required_run_variants"]
    assert isinstance(count, ast.IfExp) and isinstance(count.test, ast.Name)
    assert count.test.id == "polling_correction_only"
    assert count.orelse.test.id == "ordinary_only"
    assert ast.literal_eval(count.orelse.body) == 174
    assert ast.literal_eval(count.orelse.orelse) == 176
    assert ast.literal_eval(defaults["ordinary_only"]) is False


def test_ordinary_scope_excludes_only_exact_syscall_audit_and_cannot_claim_full_pass():
    source = (ROOT / "tests/fixtures/source_facts/boundary_supervisor.py").read_text()
    tree = ast.parse(source)
    qualify = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "qualify")
    assignments = {t.id: n.value for n in ast.walk(qualify) if isinstance(n, ast.Assign)
                   for t in n.targets if isinstance(t, ast.Name)}
    expression = compile(ast.Expression(assignments["excluded"]), "<scope>", "eval")
    assert eval(expression, {"ordinary_only": False}) == []
    assert eval(expression, {"ordinary_only": True}) == [
        "--deselect=tests/unit/test_source_fact_lifecycle_completion.py::test_completion_owned_pipeline_syscall_authority_audit"]
    summary = assignments["summary"]
    keys = dict(zip((ast.literal_eval(k) for k in summary.keys), summary.values))
    full = compile(ast.Expression(keys["full176_qualified"]), "<qualified>", "eval")
    for passed in (False, True):
        for polling in (False, True):
            for ordinary in (False, True):
                assert eval(full, {"passed": passed, "polling_correction_only": polling,
                                   "ordinary_only": ordinary}) == (passed and not polling and not ordinary)
    assert 'if ordinary_only: full_counts["unrun"] += 2' in source
    assert 'names.discard("test_completion_owned_pipeline_syscall_authority_audit")' in source
