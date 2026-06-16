from __future__ import annotations

"""
CLI: показать решения политики (AUTO/NEEDS_APPROVAL/FORBIDDEN) для ScenarioPlan.

Использует:
- Scenario DSL (JSON/YAML c полями goal/steps/required_autonomy/overall_risk/...);
- Autonomy Policy (DEFAULT_POLICIES из src/ai/scenario_policy.py).

Пример:
    python scripts/cli/print_scenario_decisions.py docs/architecture/examples/scenario_plan_ba_dev_qa.json A2_non_prod_changes
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml

from src.ai.scenario_hub import (
    AutonomyLevel,
    ScenarioGoal,
    ScenarioPlan,
    ScenarioRiskLevel,
    ScenarioStep,
)
from src.ai.scenario_policy import assess_plan_execution


def _load_plan(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _dict_to_scenario_goal(data: Dict[str, Any]) -> ScenarioGoal:
    return ScenarioGoal(
        id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        constraints=data.get("constraints", {}),
        success_criteria=data.get("success_criteria", []),
    )


def _dict_to_scenario_step(data: Dict[str, Any]) -> ScenarioStep:
    return ScenarioStep(
        id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        risk_level=ScenarioRiskLevel(data["risk_level"]),
        autonomy_required=AutonomyLevel(data["autonomy_required"]),
        checks=data.get("checks", []),
        executor=data.get("executor", "agent:default"),
        metadata=data.get("metadata", {}),
    )


def _dict_to_scenario_plan(data: Dict[str, Any]) -> ScenarioPlan:
    # Конструируем полноценные dataclass-объекты (ScenarioGoal/ScenarioStep),
    # т.к. политика выполнения читает step.risk_level и step.id у объектов, а не dict.
    return ScenarioPlan(
        id=data["id"],
        goal=_dict_to_scenario_goal(data["goal"]),
        steps=[_dict_to_scenario_step(step) for step in data["steps"]],
        required_autonomy=AutonomyLevel(data["required_autonomy"]),
        overall_risk=ScenarioRiskLevel(data["overall_risk"]),
        context=data.get("context", {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Print Scenario Policy decisions for ScenarioPlan.")
    parser.add_argument("path", type=str, help="Path to ScenarioPlan file (JSON or YAML).")
    parser.add_argument(
        "autonomy",
        type=str,
        choices=[
            "A0_propose_only",
            "A1_safe_automation",
            "A2_non_prod_changes",
            "A3_restricted_prod",
        ],
        help="Autonomy level to evaluate.",
    )
    args = parser.parse_args()

    plan_dict = _load_plan(Path(args.path))
    plan = _dict_to_scenario_plan(plan_dict)
    autonomy_level = AutonomyLevel(args.autonomy)

    decisions = assess_plan_execution(plan, autonomy_level)

    output = {
        "scenario_id": plan.id,
        "autonomy": autonomy_level.value,
        "decisions": {step_id: decision.value for step_id, decision in decisions.items()},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


