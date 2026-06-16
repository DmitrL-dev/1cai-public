
#!/usr/bin/env python3
"""
Validate spec-driven feature documents.

Checks that required files (plan.md, spec.md, tasks.md, research.md) exist in
each feature directory under docs/research/features/, and that template
placeholders ({{FEATURE_TITLE}}, {{DATE}}, {{OWNER}}) or TODO markers are not left unedited.

Usage:
    python scripts/research/check_feature.py              # validate all features
    python scripts/research/check_feature.py --feature slug

Exit codes:
    0 - success
    1 - validation errors
    2 - configuration/usage error
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

FEATURES_BASE = Path("docs/research/features")
REQUIRED_FILES = ("plan.md", "spec.md", "tasks.md", "research.md")
PLACEHOLDER_MARKERS = ("{{FEATURE_TITLE}}", "{{DATE}}", "{{OWNER}}")


@dataclass
class Issue:
    feature: str
    file: str
    message: str


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate spec-driven feature documents.")
    parser.add_argument(
        "--feature",
        help="Specific feature slug to validate. If omitted, all directories under docs/research/features are checked.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=FEATURES_BASE,
        help=f"Base directory with features (default: {FEATURES_BASE})",
    )
    parser.add_argument(
        "--allow-todo",
        action="store_true",
        help="Allow TODO markers to remain in documents (default: false).",
    )
    return parser.parse_args(list(argv))


def list_features(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted([path for path in base_dir.iterdir() if path.is_dir()])


def check_file_content(path: Path, allow_todo: bool) -> List[str]:
    issues: List[str] = []
    content = path.read_text(encoding="utf-8")
    for marker in PLACEHOLDER_MARKERS:
        if marker in content:
            issues.append(f"Содержит незаполненный шаблон '{marker}'")
    if not allow_todo and "TODO" in content:
        issues.append("Содержит TODO — заполните или удалите")
    if not content.strip():
        issues.append("Файл пустой")
    return issues


def validate_feature(feature_dir: Path, allow_todo: bool) -> List[Issue]:
    issues: List[Issue] = []
    for filename in REQUIRED_FILES:
        file_path = feature_dir / filename
        if not file_path.exists():
            issues.append(Issue(feature_dir.name, filename, "Файл отсутствует"))
            continue
        problems = check_file_content(file_path, allow_todo=allow_todo)
        for problem in problems:
            issues.append(Issue(feature_dir.name, filename, problem))
    return issues


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    base_dir: Path = args.base_dir

    if args.feature:
        feature_dirs = [base_dir / args.feature]
    else:
        feature_dirs = list_features(base_dir)

    if not feature_dirs:
        print(f"[check_feature] Не найдено каталогов в {base_dir}. Создайте feature через 'make feature-init'.")
        return 0

    all_issues: List[Issue] = []
    missing_dirs: List[Tuple[str, Path]] = []

    for feature_dir in feature_dirs:
        if not feature_dir.exists():
            missing_dirs.append((feature_dir.name, feature_dir))
            continue
        all_issues.extend(validate_feature(feature_dir, allow_todo=args.allow_todo))

    for slug, path in missing_dirs:
        print(f"[check_feature] Каталог не найден: {path}")

    if all_issues:
        print("[check_feature] Найдены проблемы:")
        for issue in all_issues:
            print(f"  - [{issue.feature}] {issue.file}: {issue.message}")
        print("[check_feature] Исправьте указанные файлы и повторите проверку.")
        return 1

    print("[check_feature] Все проверенные документы заполнены корректно.")
    return 1 if missing_dirs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


