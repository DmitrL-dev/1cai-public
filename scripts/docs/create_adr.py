
#!/usr/bin/env python3
"""
Create a new Architecture Decision Record based on a slug.

Usage:
    python scripts/docs/create_adr.py adopt-new-tool
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

ADR_DIR = Path("docs/architecture/adr")
INDEX_FILE = ADR_DIR / "README.md"
ADR_TEMPLATE = """# ADR-{id_str}: {title}

- **Date:** {date}
- **Status:** Proposed
- **Supersedes:** None
- **Superseded by:** _n/a_

## Context

Describe the background, forces, and requirements that led to this decision.

## Decision

Summarise the chosen solution. Detail supporting diagrams or documents.

## Consequences

- Positive impact
- Negative impact
- Follow up actions
"""


def slug_to_title(slug: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", slug.lower()).strip().split()
    return " ".join(w.capitalize() for w in words)


def get_next_id() -> int:
    existing_ids = []
    for path in ADR_DIR.glob("ADR-*.md"):
        match = re.match(r"ADR-(\d{4})-", path.name)
        if match:
            existing_ids.append(int(match.group(1)))
    return max(existing_ids, default=0) + 1


def append_to_index(id_str: str, title: str, status: str) -> None:
    if not INDEX_FILE.exists():
        return
    lines = INDEX_FILE.read_text(encoding="utf-8").splitlines()
    insertion_index = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("| ADR-"):
            insertion_index = idx + 1
    if insertion_index is None:
        lines.append(f"| ADR-{id_str} | {title} | {status} | { _dt.date.today()} |")
    else:
        lines.insert(insertion_index, f"| ADR-{id_str} | {title} | {status} | { _dt.date.today()} |")
    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python scripts/docs/create_adr.py <slug>", file=sys.stderr)
        return 2
    slug = argv[0]
    if not re.match(r"^[a-z0-9-]+$", slug):
        print("Slug must contain lowercase letters, digits and hyphen", file=sys.stderr)
        return 2
    ADR_DIR.mkdir(parents=True, exist_ok=True)
    next_id = get_next_id()
    id_str = f"{next_id:04d}"
    title = slug_to_title(slug)
    filename = ADR_DIR / f"ADR-{id_str}-{slug}.md"
    if filename.exists():
        print(f"ADR already exists: {filename}", file=sys.stderr)
        return 1
    content = ADR_TEMPLATE.format(
        id_str=id_str,
        title=title,
        date=_dt.date.today().isoformat(),
    )
    filename.write_text(content, encoding="utf-8")
    append_to_index(id_str, title, "Proposed")
    print(f"Created {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

