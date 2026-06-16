
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger("ba_pipeline")


def load_json_env(env_var: str, default: Optional[Iterable[Dict[str, Any]]] = None) -> Iterable[Dict[str, Any]]:
    raw = os.getenv(env_var)
    if not raw:
        return default or []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        raise ValueError("Expected list payload")
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", env_var, exc)
        return default or []


def figure_output_dir(output_dir: Optional[str]) -> Path:
    path = Path(output_dir or os.getenv("BA_PIPELINE_OUTPUT_DIR", "data/ba_intel"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose or os.getenv("BA_PIPELINE_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

