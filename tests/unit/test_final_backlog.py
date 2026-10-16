"""Every canonical requirement ID is classified exactly once in the backlog."""
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ID = re.compile(r"`([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)`")


def test_backlog_classifies_each_registry_requirement_once():
    registry = re.findall(
        r"^\| `([A-Z0-9-]+)` \|",
        (ROOT / "docs/product/FULL-FINAL-PLAN.md").read_text("utf-8"),
        re.M,
    )
    assert len(registry) == len(set(registry)) == 127
    text = (ROOT / "docs/product/BACKLOG.md").read_text("utf-8")
    counts = Counter(name for name in ID.findall(text) if name in set(registry))
    assert set(counts) == set(registry), sorted(set(registry) - set(counts))
    assert [name for name, count in counts.items() if count != 1] == []
    unknown = sorted(
        name
        for name in ID.findall(text)
        if name not in set(registry) and re.fullmatch(r"[A-Z]+(?:-[A-Z0-9]+)*-\d{2}", name)
    )
    assert unknown == []
