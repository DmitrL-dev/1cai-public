
"""
Utilities for working with ML dataset configuration.

The configuration file lives in config/ml_datasets.json and describes
available dataset presets (paths, defaults, metadata).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config" / "ml_datasets.json"


def load_configs() -> Dict[str, Dict[str, Any]]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"ML datasets configuration not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("ml_datasets.json must contain a JSON object at top level")

    return data


def get_config(name: str) -> Dict[str, Any]:
    configs = load_configs()
    try:
        return configs[name]
    except KeyError as exc:
        raise KeyError(f"Unknown ML dataset config '{name}'. "
                       f"Available: {', '.join(sorted(configs))}") from exc


def format_config_info(name: str, config: Dict[str, Any]) -> str:
    lines = [
        f"Dataset: {name}",
        f"  Description : {config.get('description', '—')}",
        f"  Dataset file: {config.get('dataset_host', '—')}",
        f"  QA file     : {config.get('qa_host', '—')}",
        f"  Model (host): {config.get('model_host', '—')}",
        f"  Epochs (def): {config.get('default_epochs', '—')}",
        f"  Eval report : {config.get('eval_report', '—')}",
    ]
    notes = config.get("notes")
    if notes:
        lines.append(f"  Notes       : {notes}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ML dataset configuration")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available dataset names and exit",
    )
    parser.add_argument(
        "--name",
        help="Dataset name to inspect (default: first available)",
    )
    parser.add_argument(
        "--field",
        help="Return specific field value (requires --name)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print human-readable info about a dataset (requires --name)",
    )

    args = parser.parse_args()

    configs = load_configs()

    if args.list:
        for key in sorted(configs):
            print(key)
        return

    name = args.name or next(iter(configs))

    config = get_config(name)

    if args.field:
        value = config.get(args.field)
        if value is None:
            raise SystemExit(f"Field '{args.field}' is not defined for dataset '{name}'")
        print(value)
        return

    if args.info:
        print(format_config_info(name, config))
        return

    # Default behaviour: print JSON for dataset
    print(json.dumps({name: config}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

