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


def test_source_fact_job_requires_default_full_supervisor_before_installed_smoke():
    job = workflow("source-facts-ci.yml")["jobs"]["linux-source-facts"]
    assert job["name"] == "Linux source facts (176 + installed wheel)"
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["defaults"]["run"]["shell"] == "bash"
    assert "if" not in job and "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in job["steps"])
    full = next(s for s in job["steps"] if s.get("name") ==
                "Required default supervised 176-variant qualification")
    smoke = next(s for s in job["steps"] if s.get("name") ==
                 "Required installed-wheel source-fact smoke")
    assert "if" not in full and "if" not in smoke
    assert job["steps"].index(full) < job["steps"].index(smoke)
    # Exact argv excludes subset flags, shell success coercion and alternate runners.
    assert shlex.split(full["run"]) == [
        "$BUILD_ROOT/tools/bin/python", "-I", "-B",
        "$SOURCE_ROOT/tests/fixtures/source_facts/boundary_supervisor.py",
        "--root", "$SOURCE_ROOT", "--pins", "$EVIDENCE/pins.json",
        "--pins-sha256", "$(cat $EVIDENCE/pins.sha256)",
        "--output", "$EVIDENCE/full176",
    ]
    assert "--polling-correction-only" not in "\n".join(step.get("run", "") for step in job["steps"])


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
    assert ast.literal_eval(count.orelse) == 176
