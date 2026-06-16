
#!/usr/bin/env python3
"""
Сравнение ответов двух LLM для оценки качества после переключения.

До внедрения реальных вызовов скрипт работает как заглушка и формирует
отчёт с рекомендациями по ручной проверке.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сравнение ответов LLM (placeholder)")
    parser.add_argument("--baseline", required=True, help="Имя эталонного провайдера")
    parser.add_argument("--candidate", required=True, help="Имя нового провайдера")
    parser.add_argument("--output", type=Path, default=Path("output/llm_diff_report.json"), help="Файл отчёта")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "status": "placeholder",
        "notes": "Реальная проверка будет добавлена после интеграции LLM gateway и тестов.",
        "recommendation": "Провести ручное сравнение ключевых сценариев и зафиксировать результаты в отчёте.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Comparison placeholder report saved to {args.output}")


if __name__ == "__main__":
    main()

