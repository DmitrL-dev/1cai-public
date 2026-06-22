import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_print_scenario_decisions_cli_runs(tmp_path: Path):
    # Используем готовый пример ScenarioPlan
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = (
        repo_root
        / "docs"
        / "architecture"
        / "examples"
        / "scenario_plan_ba_dev_qa.json"
    )
    script_path = repo_root / "scripts" / "cli" / "print_scenario_decisions.py"

    # Запускаем CLI через sys.executable с cwd=repo_root и PYTHONPATH=repo_root,
    # чтобы импорт `src.ai` разрешался при любом окружении запуска тестов.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(script_path),
            str(plan_path),
            "A2_non_prod_changes",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, (
        f"CLI exited with {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    data = json.loads(result.stdout)

    assert data["scenario_id"] == "plan-ba-dev-qa-EXTERNAL_DEMO"
    assert data["autonomy"] == "A2_non_prod_changes"
    assert isinstance(data["decisions"], dict)
    assert data["decisions"]  # non-empty
    assert set(data["decisions"].values()) <= {"auto", "needs_approval", "forbidden"}
