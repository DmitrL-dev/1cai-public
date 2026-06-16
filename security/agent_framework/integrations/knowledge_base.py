
"""Helpers to sync results with local knowledge base JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


def append_to_jsonl(path: str | Path, payload: Mapping) -> Path:
    """Append payload as JSON line to the specified file."""

    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with target_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return target_path

