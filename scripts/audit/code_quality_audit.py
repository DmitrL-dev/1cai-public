
#!/usr/bin/env python3
"""
Код-качество аудит: запуск линтеров и форматеров.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

TOOLS = {
    "flake8": ["flake8", "--max-line-length", "120"],
    "mypy": ["mypy", "src", "--ignore-missing-imports"],
    "black": ["black", "--check", "src", "tests"],
    "isort": ["isort", "--check-only", "src", "tests"],
}


def run_tool(command: List[str], cwd: Path) -> Dict[str, any]:
    tool = command[0]
    if shutil.which(tool) is None:
        return {"tool": tool, "status": "missing"}
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
        return {"tool": tool, "status": "passed", "stdout": result.stdout.strip()}
    except subprocess.CalledProcessError as exc:
        return {
            "tool": tool,
            "status": "failed",
            "returncode": exc.returncode,
            "stdout": exc.stdout.strip(),
            "stderr": exc.stderr.strip(),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Аудит качества кода")
    parser.add_argument("--root", type=Path, default=Path("."), help="Корневой каталог проекта")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/audit/code_quality.json"),
        help="Файл для сохранения результатов",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(f"Ошибка: каталог {root} не найден")
        return 1

    results = []
    for tool_cmd in TOOLS.values():
        results.append(run_tool(tool_cmd, root))

    report = {
        "schema_version": "1.0.0",
        "root": str(root),
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    passed = sum(1 for item in results if item["status"] == "passed")
    failed = sum(1 for item in results if item["status"] == "failed")
    missing = sum(1 for item in results if item["status"] == "missing")

    print("Аудит качества кода завершён:")
    print(f"  ✓ Passed: {passed}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ⚠ Missing tools: {missing}")
    print(f"Отчёт: {args.output}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




