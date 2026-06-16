
"""Built-in presets for the security agent framework."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

PRESETS_DIR = Path(__file__).resolve().parent


def list_presets() -> Iterable[str]:
    return sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))


def get_preset_path(name: str) -> Path:
    path = PRESETS_DIR / f"{name}.yaml"
    if not path.exists():
        raise KeyError(name)
    return path


def copy_preset_to(name: str, destination: Path) -> Path:
    source = get_preset_path(name)
    destination = destination if destination.suffix else destination.with_suffix(".yaml")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination

