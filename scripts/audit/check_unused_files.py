
"""
Check for potentially unused files (experimental)
-------------------------------------------------

Скрипт пытается найти кандидатов на "мертвые" файлы:
- те, чьи пути/имена нигде не упоминаются (кроме самих файлов и git ls-files);
- при этом игнорирует заведомо архивные/backup-папки.

ВАЖНО:
- Скрипт НИЧЕГО не удаляет, только печатает отчёт в stdout.
- Результат — список кандидатов, которые требуют ручной проверки.

Пример запуска:

    python scripts/audit/check_unused_files.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Set

ROOT = Path(__file__).resolve().parents[2]


IGNORED_DIR_PREFIXES = [
    "analysis/",
    "output/",
    "docs/09-archive/",
    "docs/architecture/checksums/",
    "src/",
    "tests/",
    "frontend-portal/",
    "supabase/",
    "integrations/",
    "security/agent_framework/",
    "edge-functions/",
    "infrastructure/",
    ".github/",
    ".git/",
    "venv/",
    ".venv/",
]

# Файлы, которые считаются "исключёнными" из проверки (архивы, планы и т.п.)
IGNORED_FILES = {
    "analysis/git_ls_files.txt",
}


def is_ignored_path(rel_path: str) -> bool:
    # Игнорируем служебные .gitkeep (держат пустые директории в git)
    if rel_path.endswith("/.gitkeep"):
        return True
    for prefix in IGNORED_DIR_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    return rel_path in IGNORED_FILES


def git_ls_files() -> List[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return files


def collect_search_space(files: Iterable[str]) -> List[Path]:
    """Файлы, в которых мы ищем упоминания (исключая бинарные/крупные по расширениям)."""
    text_extensions = {
        ".py",
        ".md",
        ".yaml",
        ".yml",
        ".json",
        ".txt",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".tsx",
    }
    search_paths: List[Path] = []
    for rel in files:
        if is_ignored_path(rel):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in text_extensions:
            search_paths.append(path)
    return search_paths


def file_mentions_path(path_to_check: str, search_path: Path) -> bool:
    """
    Проверить, упоминается ли относительный путь (или basename) файла в данном search_path.

    Учитываем:
    - полный относительный путь (Unix-стиль с '/');
    - basename файла.
    """
    try:
        content = search_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    rel_unix = path_to_check.replace("\\", "/")
    basename = os.path.basename(rel_unix)

    return (rel_unix in content) or (basename in content)


def main() -> None:
    all_files = git_ls_files()

    # Подготовим пространство поиска (где ищем ссылки)
    search_paths = collect_search_space(all_files)
    search_paths_set: Set[Path] = set(search_paths)

    candidates: Dict[str, List[str]] = {}

    for rel in all_files:
        if is_ignored_path(rel):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue

        # Архивные/legacy файлы явно не трогаем (по имени каталога)
        parts = rel.split("/")
        if "legacy" in parts or "archive" in parts or "backup" in parts:
            continue

        # Ищем упоминания файла в других файлах
        mentioned_in: List[str] = []
        for search_path in search_paths:
            # Не считаем упоминания в самом себе
            if search_path == path:
                continue
            if file_mentions_path(rel, search_path):
                mentioned_in.append(str(search_path.relative_to(ROOT)))
                # достаточно одного упоминания, чтобы считать файл используемым
                break

        if not mentioned_in:
            candidates[rel] = []

    if not candidates:
        print("Нет очевидных кандидатов на неиспользуемые файлы (по простому анализу ссылок).")
        return

    print("Кандидаты на неиспользуемые файлы (ТРЕБУЮТ ручной проверки):")
    for rel in sorted(candidates.keys()):
        print(f" - {rel}")


if __name__ == "__main__":
    main()


