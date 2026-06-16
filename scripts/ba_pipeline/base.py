
from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def ensure_output_dir(base_dir: Path, collector_name: str) -> Path:
    """Create dated directory for collector outputs."""
    date_folder = datetime.now(timezone.utc).strftime("%Y%m%d")
    collector_dir = base_dir / collector_name
    collector_dir.mkdir(parents=True, exist_ok=True)
    target_dir = collector_dir / date_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


@dataclass
class CollectorResult:
    collector: str
    status: str
    records_count: int = 0
    output_file: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collector": self.collector,
            "status": self.status,
            "records_count": self.records_count,
            "output_file": str(self.output_file) if self.output_file else None,
            "metadata": self.metadata,
        }


class BaseCollector(abc.ABC):
    """Base class for BA data collectors."""

    name: str = "base"
    description: str = ""

    def __init__(self, *, now: Optional[datetime] = None) -> None:
        self.now = now or datetime.now(timezone.utc)

    @abc.abstractmethod
    def collect(
        self,
        *,
        output_dir: Path,
        since: Optional[datetime],
    ) -> CollectorResult:
        """Collect data and persist JSON payload to `output_dir`."""

    def _write_output(self, output_dir: Path, payload: List[Dict[str, Any]]) -> Path:
        timestamp = self.now.strftime("%Y%m%dT%H%M%SZ")
        file_path = output_dir / f"{self.name}_{timestamp}.json"
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "collector": self.name,
                    "generated_at": self.now.isoformat(),
                    "records": payload,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        return file_path

    @staticmethod
    def parse_since(days: Optional[int]) -> Optional[datetime]:
        if days is None:
            return None
        return datetime.now(timezone.utc) - timedelta(days=days)

