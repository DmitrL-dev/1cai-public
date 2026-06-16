
#!/usr/bin/env python3
"""
Симуляция health-check провайдеров LLM.

Позволяет проиграть инцидент: пометить провайдера как «недоступного» и увидеть,
как будет выглядеть отчёт. Реальные изменения конфигурации не выполняются.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List

from src.services.llm_provider_manager import load_llm_provider_manager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Моделирование health-check провайдеров LLM")
    parser.add_argument("--down", nargs="*", default=[], help="Провайдеры, которые считаются недоступными")
    parser.add_argument("--output", default=None, help="Путь для сохранения отчёта в JSON")
    return parser.parse_args()


def build_report(down: List[str]) -> Dict[str, Dict[str, str]]:
    manager = load_llm_provider_manager()
    report: Dict[str, Dict[str, str]] = {}

    for provider in manager.available_providers():
        status = "down" if provider.name in down else "up"
        report[provider.name] = {
            "status": status,
            "base_url": provider.base_url,
            "priority": str(provider.priority),
        }

    return report


def main() -> None:
    args = parse_args()
    report = build_report(args.down)

    print("LLM Health Simulation\n---------------------")
    for name, data in report.items():
        marker = "❌" if data["status"] == "down" else "✅"
        print(f"{marker} {name:15} status={data['status']} priority={data['priority']} url={data['base_url']}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nОтчёт сохранён в {args.output}")


if __name__ == "__main__":
    main()



