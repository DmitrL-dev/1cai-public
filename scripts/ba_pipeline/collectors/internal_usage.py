
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scripts.ba_pipeline.base import (BaseCollector, CollectorResult,
                                      ensure_output_dir)

logger = logging.getLogger(__name__)


class InternalUsageCollector(BaseCollector):
    """Aggregate internal telemetry exported by BA module."""

    name = "internal_usage"
    description = "Внутренние метрики использования BA-агента (SLA, запросы, feedback)."

    SOURCE_FILE_ENV = "BA_INTERNAL_USAGE_EXPORT"

    def collect(
        self,
        *,
        output_dir: Path,
        since: Optional[datetime],
    ) -> CollectorResult:
        export_path = Path(os.environ.get(self.SOURCE_FILE_ENV, "")).expanduser()
        records: List[Dict[str, str]] = []
        metadata: Dict[str, str] = {"source": "stub"}

        if export_path.is_file():
            try:
                with export_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                for row in data.get("entries", []):
                    timestamp = row.get("timestamp", self.now.isoformat())
                    if since:
                        try:
                            ts = datetime.fromisoformat(timestamp)
                            if ts < since:
                                continue
                        except ValueError:
                            logger.debug("Invalid timestamp in usage entry: %s", timestamp)
                    records.append(
                        {
                            "feature": row.get("feature"),
                            "count": row.get("count", 0),
                            "timestamp": timestamp,
                            "feedback": row.get("feedback"),
                        }
                    )
                metadata = {"source": "import", "path": str(export_path)}
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("Failed to parse internal usage export: %s", exc)

        if not records:
            records.append(
                {
                    "feature": "storytelling_generate_deck",
                    "count": 0,
                    "timestamp": self.now.isoformat(),
                    "note": "Загрузите фактические данные в BA_INTERNAL_USAGE_EXPORT.",
                }
            )

        target_dir = ensure_output_dir(output_dir, self.name)
        output_file = self._write_output(target_dir, records)
        return CollectorResult(
            collector=self.name,
            status="ok",
            records_count=len(records),
            output_file=output_file,
            metadata=metadata,
        )

