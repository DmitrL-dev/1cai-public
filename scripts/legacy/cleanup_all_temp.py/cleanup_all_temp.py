
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMP_PATTERNS = [
    "*ГОТОВ*.md",
    "*ИНСТРУКЦ*.md",
    "*ФИНАЛЬНЫЙ*.md",
    "*АРХИТ*.md",
    "*ДОРАБОТ*.md",
]


def main() -> int:
    deleted = 0

    for pattern in TEMP_PATTERNS:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            try:
                path.unlink()
                print(f"Deleted: {path.name}")
                deleted += 1
            except OSError as exc:
                print(f"Cannot delete {path.name}: {exc}")

    print(f"\nTotal deleted: {deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

