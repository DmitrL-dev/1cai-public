
#!/usr/bin/env python3
"""
Smoke-тест для проверки базовой доступности LLM бекендов.

Пока реализован как заглушка: фиксирует запуск и завершение.
После внедрения LLM Gateway сюда будет добавлена фактическая проверка генерации.
"""

import argparse
import logging
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path("config/llm_providers.yaml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-тест LLM провайдеров")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Конфигурация провайдеров")
    parser.add_argument("--provider", type=str, default=None, help="Провайдер для проверки (по умолчанию активный)")
    return parser.parse_args()


def load_active_provider(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    fallback = data.get("fallback_matrix", {})
    if fallback:
        # Берём первого упомянутого primary для справки
        role = next(iter(fallback.values()))
        if isinstance(role, dict):
            return role.get("primary")
    return None


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    provider = args.provider or load_active_provider(args.config) or "unknown"
    logging.info("LLM smoke test placeholder running (provider=%s)", provider)
    logging.info("Success: placeholder does not perform real checks yet.")


if __name__ == "__main__":
    main()

