
#!/usr/bin/env python3
"""
Проверка безопасности git-репозитория: крупные файлы, потенциальные секреты, .gitignore.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

LARGE_FILE_THRESHOLD_MB = 100
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)secret_key\s*=\s*['\"]?[A-Za-z0-9+/]{20,}"),
    re.compile(r"(?i)api[-_]?key\s*=\s*['\"]?[A-Za-z0-9+/]{20,}"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{20,}"),
]
DEFAULT_WHITELIST = {
    "tests/fixtures/sample_key.pem",
    "docs/examples/.env.example",
}


def scan_large_files(root: Path, threshold_mb: int) -> List[Dict[str, any]]:
    results = []
    threshold_bytes = threshold_mb * 1024 * 1024
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= threshold_bytes:
            results.append(
                {
                    "path": str(path.relative_to(root)),
                    "size_mb": round(size / 1024 / 1024, 2),
                }
            )
    return results


def scan_secrets(root: Path, whitelist: set[str]) -> List[Dict[str, any]]:
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = str(path.relative_to(root))
        if rel in whitelist:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        matches = []
        for pattern in SECRET_PATTERNS:
            for match in pattern.findall(content):
                matches.append(match if isinstance(match, str) else match[0])
        if matches:
            findings.append({"path": rel, "matches": matches[:5]})
    return findings


def check_gitignore(root: Path) -> Dict[str, List[str]]:
    required = {".env", "*.key", "*.pem", "secrets/"}
    try:
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    except OSError:
        return {"missing": sorted(required)}
    missing = [pattern for pattern in required if pattern not in gitignore]
    return {"missing": missing}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверка git-репозитория на безопасность")
    parser.add_argument("--root", type=Path, default=Path("."), help="Корень проекта")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/audit/git_safety.json"),
        help="Файл для сохранения результатов",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=LARGE_FILE_THRESHOLD_MB,
        help="Порог для больших файлов (MB)",
    )
    parser.add_argument(
        "--whitelist",
        nargs="*",
        default=list(DEFAULT_WHITELIST),
        help="Относительные пути файлов, которые можно пропускать при проверке секретов",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(f"Ошибка: каталог {root} не найден")
        return 1

    report = {
        "schema_version": "1.0.0",
        "root": str(root),
        "large_files": scan_large_files(root, args.threshold),
        "secrets": scan_secrets(root, set(args.whitelist)),
        "gitignore": check_gitignore(root),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    print("Проверка git завершена. Отчёт сохранён в", args.output)
    print(f"  Файлов > {args.threshold}MB: {len(report['large_files'])}")
    print(f"  Потенциальных секретов: {len(report['secrets'])}")
    print(f"  Отсутствующих паттернов .gitignore: {len(report['gitignore']['missing'])}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




