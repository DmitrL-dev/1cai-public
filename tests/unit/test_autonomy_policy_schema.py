
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.ai.scenario_policy import DEFAULT_POLICIES

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs" / "architecture" / "AUTONOMY_POLICY_SCHEMA.json"
EXTERNAL_POLICY_PATH = (
    ROOT / "docs" / "architecture" / "examples" / "autonomy_policy_default.json"
)


def _load_schema():
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_default_policies_conform_to_schema():
    schema = _load_schema()
    validator = Draft202012Validator(schema)

    # Внутренняя конфигурация (DEFAULT_POLICIES)
    config = {
        autonomy.value: {
            "max_auto_risk": policy.max_auto_risk.value,
            "max_allowed_risk": policy.max_allowed_risk.value,
        }
        for autonomy, policy in DEFAULT_POLICIES.items()
    }

    errors = list(validator.iter_errors(config))
    assert (
        not errors
    ), f"AutonomyPolicy config does not match schema: {[e.message for e in errors]}"

    # Внешний JSON-пример
    with EXTERNAL_POLICY_PATH.open("r", encoding="utf-8") as f:
        external_config = json.load(f)
    errors = list(validator.iter_errors(external_config))
    assert (
        not errors
    ), f"External AutonomyPolicy example violates schema: {[e.message for e in errors]}"
