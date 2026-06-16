
#!/usr/bin/env python3
"""
Полный структурный аудит проекта.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable

DEFAULT_IGNORE = {
    "__pycache__",
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".cache",
    ".pytest_cache",
    "1c_configurations",
}

DEFAULT_HASH_EXTS = {".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml", ".md"}


def iter_files(root: Path, ignore: Iterable[str]) -> Iterable[Path]:
    ignore_set = set(ignore)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_set]
        for filename in filenames:
            yield Path(dirpath) / filename


def hash_file(path: Path, chunk_size: int = 8192) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_structure(root: Path, ignore: Iterable[str]) -> Dict[str, any]:
    files = list(iter_files(root, ignore))
    ext_counts = defaultdict(int)
    size_buckets = defaultdict(list)
    large_files = []
    duplicates = defaultdict(list)
    hash_cache = {}
    total_size = 0

    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue

        ext = path.suffix.lower() or "(no extension)"
        ext_counts[ext] += 1
        size_buckets[ext].append(stat.st_size)
        total_size += stat.st_size

        if stat.st_size > 1 * 1024 * 1024:
            large_files.append(
                {
                    "path": str(path.relative_to(root)),
                    "size_mb": stat.st_size / 1024 / 1024,
                    "ext": ext,
                }
            )

        if stat.st_size <= 10 * 1024 * 1024 and ext in DEFAULT_HASH_EXTS:
            try:
                digest = hash_file(path)
                if digest in hash_cache and hash_cache[digest] == stat.st_size:
                    duplicates[digest].append(str(path.relative_to(root)))
                else:
                    hash_cache[digest] = stat.st_size
                    duplicates[digest].append(str(path.relative_to(root)))
            except OSError:
                continue

    large_files.sort(key=lambda item: item["size_mb"], reverse=True)
    duplicate_groups = {k: v for k, v in duplicates.items() if len(v) > 1}

    return {
        "total_files": len(files),
        "total_size_mb": total_size / 1024 / 1024,
        "file_types": dict(ext_counts),
        "size_buckets": {
            ext: {
                "count": len(sizes),
                "total_mb": sum(sizes) / 1024 / 1024,
            }
            for ext, sizes in size_buckets.items()
        },
        "large_files": large_files[:50],
        "duplicates": duplicate_groups,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Структурный аудит проекта")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Корень проекта для аудита",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/audit/project_structure.json"),
        help="Файл для сохранения отчёта",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=list(DEFAULT_IGNORE),
        help="Список директорий для игнорирования",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()

    if not root.exists():
        print(f"Ошибка: каталог {root} не найден")
        return 1

    print("=" * 80)
    print(f"СТРУКТУРНЫЙ АУДИТ: {root}")
    print("=" * 80)

    report = analyze_structure(root, args.ignore)
    report["schema_version"] = "1.0.0"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    print(f"\n✓ Отчёт сохранён: {args.output}")
    print(f"Файлов просканировано: {report['total_files']:,}")
    print(f"Общий размер: {report['total_size_mb'] / 1024:.2f} GB")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




