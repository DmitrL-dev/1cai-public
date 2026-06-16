
#!/usr/bin/env python3
"""
Проверка лицензий зависимостей проекта.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

DEFAULT_WHITELIST = {"MIT", "BSD", "Apache", "Apache-2.0", "ISC", "LGPL"}


def run_pip_licenses(root: Path) -> Dict[str, any]:
    cmd = ["pip-licenses", "--format", "json", "--with-authors", "--with-urls"]
    if shutil.which("pip-licenses") is None:
        return {"status": "missing", "dependencies": []}
    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return {"status": "ok", "dependencies": data}
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "returncode": exc.returncode,
            "stderr": exc.stderr.strip(),
            "dependencies": [],
        }


def classify_licenses(dependencies: List[Dict[str, any]], whitelist: set[str]) -> Dict[str, List[Dict[str, any]]]:
    allowed: List[Dict[str, any]] = []
    risky: List[Dict[str, any]] = []
    unknown: List[Dict[str, any]] = []

    for dep in dependencies:
        license_name = dep.get("License", "").strip()
        entry = {
            "name": dep.get("Name"),
            "version": dep.get("Version"),
            "license": license_name,
            "url": dep.get("URL"),
            "author": dep.get("Author"),
        }
        if not license_name:
            unknown.append(entry)
        elif any(label for label in whitelist if label.lower() in license_name.lower()):
            allowed.append(entry)
        else:
            risky.append(entry)
    return {"allowed": allowed, "risky": risky, "unknown": unknown}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Аудит лицензий зависимостей")
    parser.add_argument("--root", type=Path, default=Path("."), help="Корень проекта")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/audit/license_audit.json"),
        help="Куда сохранить отчёт",
    )
    parser.add_argument(
        "--whitelist",
        nargs="*",
        default=list(DEFAULT_WHITELIST),
        help="Лицензии, считающиеся безопасными",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(f"Ошибка: каталог {root} не найден")
        return 1

    licenses_info = run_pip_licenses(root)
    if licenses_info["status"] == "missing":
        print("Инструмент pip-licenses не установлен. Установите его: pip install pip-licenses")
        return 1

    classified = classify_licenses(licenses_info.get("dependencies", []), set(args.whitelist))
    report = {
        "schema_version": "1.0.0",
        "root": str(root),
        "status": licenses_info["status"],
        "summary": {
            "allowed": len(classified["allowed"]),
            "risky": len(classified["risky"]),
            "unknown": len(classified["unknown"]),
        },
        "details": classified,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    print("Аудит лицензий завершён:")
    print(f"  Безопасные: {report['summary']['allowed']}")
    print(f"  Требуют проверки: {report['summary']['risky']}")
    print(f"  Неопределённые: {report['summary']['unknown']}")
    print(f"Отчёт: {args.output}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




