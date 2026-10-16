"""Current pair claims follow the single READINESS heading; history is kept."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_version_claims", ROOT / "scripts/release/check_version_claims.py"
)
claims = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(claims)


def tree(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")
    return tmp_path


READY = "# Готовность\n\n## Текущая опубликованная пара — Core dev20 / Companion 0.1.21\n"


def test_repository_claims_match_the_published_pair():
    pair, findings = claims.scan(ROOT)
    assert pair == {"core": "0.1.0.dev19", "companion": "0.1.20"}
    assert findings == []


def test_stale_pair_and_front_door_tag_are_reported(tmp_path):
    root = tree(
        tmp_path,
        {
            "docs/product/READINESS.md": READY,
            "README.md": "Опубликованы Core dev19 / Companion 0.1.20 и core-v0.1.0-dev19.\n",
            "docs/product/GUIDE.md": "Пара Core 0.1.0.dev19 / Companion 0.1.20.\n",
            "docs/product/OTHER.md": "См. [тег](https://x/core-v0.1.0-dev11).\n",
        },
    )
    pair, findings = claims.scan(root)
    assert pair == {"core": "0.1.0.dev20", "companion": "0.1.21"}
    assert {(f["file"], f["kind"], f["claim"]) for f in findings} == {
        ("README.md", "pair", "dev19 / 0.1.20"),
        ("README.md", "core_tag", "core-v0.1.0-dev19"),
        ("docs/product/GUIDE.md", "pair", "dev19 / 0.1.20"),
    }
    assert claims.main(["--root", str(root)]) == 1


def test_history_sections_dated_and_record_files_are_preserved(tmp_path):
    root = tree(
        tmp_path,
        {
            "docs/product/READINESS.md": READY
            + "\n## Исторический статус\n\nПара Core dev17 / Companion 0.1.18.\n"
            + "\n## Дальше\n\nCore dev20 / Companion 0.1.21.\n",
            "docs/product/PLAN-20261015.md": "Core dev19 / Companion 0.1.20\n",
            "docs/product/SERVICE-DEV11.md": "Core dev11 / Companion 0.1.11\n",
            "docs/product/evidence/x.md": "Core dev1 / Companion 0.1.1\n",
            "releases/core/notes.md": "Core dev2 / Companion 0.1.2\n",
        },
    )
    assert claims.scan(root)[1] == []
    assert claims.main(["--root", str(root)]) == 0


def test_readiness_must_declare_exactly_one_pair(tmp_path):
    root = tree(tmp_path, {"docs/product/READINESS.md": READY + READY})
    with pytest.raises(ValueError):
        claims.scan(root)
