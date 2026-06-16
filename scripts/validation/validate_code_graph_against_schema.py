
from __future__ import annotations

"""
Validate example Code Graph export against JSON Schema.

Запуск:
    python scripts/validation/validate_code_graph_against_schema.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs" / "architecture" / "CODE_GRAPH_SCHEMA.json"
EXAMPLE_PATH = ROOT / "docs" / "architecture" / "examples" / "code_graph_minimal.json"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    schema = _load_json(SCHEMA_PATH)
    example = _load_json(EXAMPLE_PATH)

    validator = Draft202012Validator(schema)
    errors: List[str] = [
        f"{e.message} (path={list(e.path)})"
        for e in sorted(validator.iter_errors(example), key=str)
    ]

    if errors:
        print("Code Graph example validation FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    print("Code Graph example validation OK.")


if __name__ == "__main__":
    main()


