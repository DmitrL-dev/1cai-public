
#!/usr/bin/env python3
"""
Фиксация выбранного LLM-провайдера для приложения.

Скрипт записывает выбор в файл output/current_llm_backend.json.
В дальнейшем приложение сможет читать это состояние и применять нужную конфигурацию.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

CONFIG_PATH = Path("config/llm_providers.yaml")
STATE_PATH = Path("output/current_llm_backend.json")


def load_providers(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Не найден конфиг провайдеров: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("providers", {})


def write_state(provider: str, data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider,
        "metadata": {
            "base_url": data.get("base_url"),
            "type": data.get("type"),
            "priority": data.get("priority"),
        },
    }
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Переключение LLM-провайдера")
    parser.add_argument("--provider", required=True, help="Имя провайдера из config/llm_providers.yaml")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Путь к YAML с конфигурацией провайдеров")
    args = parser.parse_args()

    providers = load_providers(Path(args.config))
    if args.provider not in providers:
        raise SystemExit(f"Провайдер {args.provider} не найден в {args.config}")

    provider_data = providers[args.provider]
    write_state(args.provider, provider_data)
    print(f"LLM provider set to {args.provider} (state: {STATE_PATH})")


if __name__ == "__main__":
    main()

