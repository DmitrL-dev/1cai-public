
from __future__ import annotations

"""
Generate a simple JSON conformance report for 1C AI Stack standards.

Проверяет:
- Scenario DSL examples (internal + external) против SCENARIO_DSL_SCHEMA.json;
- Autonomy Policy examples (DEFAULT_POLICIES + external JSON) против AUTONOMY_POLICY_SCHEMA.json.

Запуск:
    python scripts/validation/check_conformance_report.py
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from src.ai.scenario_examples import (example_ba_dev_qa_scenario,
                                      example_dr_rehearsal_scenario)
from src.ai.scenario_policy import DEFAULT_POLICIES

ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_object(
    schema: Dict[str, Any], instance: Any, name: str
) -> List[str]:
    validator = Draft202012Validator(schema)
    errors: List[str] = []
    for error in sorted(validator.iter_errors(instance), key=str):
        errors.append(f"{name}: {error.message} (path={list(error.path)})")
    return errors


def main() -> None:
    report: Dict[str, Any] = {
        "scenario_dsl": {"ok": True, "errors": []},
        "autonomy_policy": {"ok": True, "errors": []},
    }

    # Scenario DSL
    scenario_schema = _load_json(
        ROOT / "docs" / "architecture" / "SCENARIO_DSL_SCHEMA.json"
    )
    scenarios_to_check: List[tuple[str, Dict[str, Any]]] = []

    # internal examples
    for key, plan in (
        ("example_ba_dev_qa_scenario", example_ba_dev_qa_scenario("DEMO_FEATURE")),
        ("example_dr_rehearsal_scenario", example_dr_rehearsal_scenario("vault")),
    ):
        data = asdict(plan)
        data.setdefault("version", "1.0.0")
        data.setdefault("spec", "scenario-dsl/v1")
        scenarios_to_check.append((key, data))

    # external JSON example
    external_plan_path = (
        ROOT
        / "docs"
        / "architecture"
        / "examples"
        / "scenario_plan_ba_dev_qa.json"
    )
    if external_plan_path.exists():
        scenarios_to_check.append(
            ("external_scenario_plan_ba_dev_qa", _load_json(external_plan_path))
        )

    for name, instance in scenarios_to_check:
        errors = _validate_object(scenario_schema, instance, name)
        if errors:
            report["scenario_dsl"]["ok"] = False
            report["scenario_dsl"]["errors"].extend(errors)

    # Autonomy Policy
    policy_schema = _load_json(
        ROOT / "docs" / "architecture" / "AUTONOMY_POLICY_SCHEMA.json"
    )
    policies_to_check: List[tuple[str, Dict[str, Any]]] = []

    internal_config = {
        autonomy.value: {
            "max_auto_risk": policy.max_auto_risk.value,
            "max_allowed_risk": policy.max_allowed_risk.value,
        }
        for autonomy, policy in DEFAULT_POLICIES.items()
    }
    policies_to_check.append(("DEFAULT_POLICIES", internal_config))

    external_policy_path = (
        ROOT
        / "docs"
        / "architecture"
        / "examples"
        / "autonomy_policy_default.json"
    )
    if external_policy_path.exists():
        policies_to_check.append(
            (
                "external_autonomy_policy_default",
                _load_json(external_policy_path),
            )
        )

    for name, instance in policies_to_check:
        errors = _validate_object(policy_schema, instance, name)
        if errors:
            report["autonomy_policy"]["ok"] = False
            report["autonomy_policy"]["errors"].extend(errors)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not (report["scenario_dsl"]["ok"] and report["autonomy_policy"]["ok"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()


