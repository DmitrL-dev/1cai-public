
from __future__ import annotations

"""
Validate example ScenarioPlan objects against Scenario DSL JSON Schema.

Запуск:
    python scripts/validation/validate_scenarios_against_schema.py

Скрипт не требует доступа к БД или внешним сервисам и может использоваться
как часть локальной проверки стандарта Scenario DSL.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from src.ai.scenario_examples import (example_ba_dev_qa_scenario,
                                      example_dr_rehearsal_scenario)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs" / "architecture" / "SCENARIO_DSL_SCHEMA.json"


def _scenario_plan_to_dict(plan) -> Dict[str, Any]:
    """Унифицированное представление ScenarioPlan для валидации по схеме."""
    # Используем dataclasses.asdict через already defined helper (ScenarioPlan — dataclass).
    from dataclasses import asdict

    data = asdict(plan)
    # Гарантируем наличие version/spec, если они не заданы в примерах.
    data.setdefault("version", "1.0.0")
    data.setdefault("spec", "scenario-dsl/v1")
    return data


def load_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_examples() -> List[str]:
    schema = load_schema()
    validator = Draft202012Validator(schema)

    examples = [
        ("ba_dev_qa", example_ba_dev_qa_scenario("DEMO_FEATURE")),
        ("dr_vault", example_dr_rehearsal_scenario("vault")),
    ]

    errors: List[str] = []
    for name, plan in examples:
        data = _scenario_plan_to_dict(plan)
        for error in sorted(validator.iter_errors(data), key=str):
            errors.append(f"{name}: {error.message} (path={list(error.path)})")
    return errors


def main() -> None:
    errors = validate_examples()
    if errors:
        print("Scenario DSL validation FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)
    print("Scenario DSL validation OK for example scenarios.")


if __name__ == "__main__":
    main()


