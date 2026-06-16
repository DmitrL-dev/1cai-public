
#!/usr/bin/env python3
"""
Scan the repository for tracked directories, которые начинаются с точки,
и формирует отчёт — выполнение требования "проверять ВСЕ .folder".

Usage:
    python scripts/audit/check_hidden_dirs.py [--fail-new]
"""

from __future__ import annotations

import argparse
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

DEFAULT_ALLOWLIST = {
    ".ci",
    ".cursor",
    ".devcontainer",
    ".github",
    ".git",
    ".memory",
    ".pytest_cache",
    ".venv",
    ".vscode",
}


def git_ls_files(repo_root: Path) -> List[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def collect_hidden_dirs(paths: Iterable[Path]) -> Dict[str, Set[Path]]:
    hidden: Dict[str, Set[Path]] = defaultdict(set)
    for rel_path in paths:
        for part in rel_path.parts[:-1]:  # только каталоги
            if part.startswith("."):
                hidden[part].add(rel_path.parent)
    return hidden


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check tracked hidden directories.")
    parser.add_argument(
        "--fail-new",
        action="store_true",
        help="Return non-zero, если обнаружены скрытые каталоги вне allowlist.",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Добавить каталог в allowlist (можно указывать несколько раз).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent.parent
    paths = git_ls_files(repo_root)
    hidden = collect_hidden_dirs(paths)

    allowlist = set(DEFAULT_ALLOWLIST) | set(args.allow)
    unexpected = {name: parents for name, parents in hidden.items() if name not in allowlist}

    print("Hidden directories report")
    print("=========================")
    if not hidden:
        print("No tracked hidden directories.")
    else:
        for name in sorted(hidden):
            marker = "[OK]" if name in allowlist else "[WARN]"
            parents = ", ".join(sorted({str(parent) or "." for parent in hidden[name]}))
            print(f"{marker} {name} -> {parents or '.'}")

    if unexpected:
        print("\nUnexpected directories detected:")
        for name, parents in sorted(unexpected.items()):
            parent_str = ", ".join(sorted({str(parent) or '.' for parent in parents}))
            print(f" - {name}: {parent_str}")
        if args.fail_new:
            return 1
    else:
        print("\nNo unexpected hidden directories.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

