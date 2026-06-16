
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from scripts.ba_pipeline.base import (BaseCollector, CollectorResult,
                                      ensure_output_dir)
from scripts.ba_pipeline.utils import load_json_env

logger = logging.getLogger(__name__)


class ConferenceCollector(BaseCollector):
    """Collect conference and standard updates."""

    name = "conference_digest"
    description = "Digest конференций (Analyst Days, IIBA, PMI) и стандартов."

    SOURCE_ENV = "BA_CONFERENCE_FEED"

    def collect(
        self,
        *,
        output_dir: Path,
        since: Optional[datetime],
    ) -> CollectorResult:
        feed = list(load_json_env(self.SOURCE_ENV))
        if not feed:
            logger.info("Conference feed not configured, using stub entries.")
            entries: Iterable[Dict[str, Any]] = [
                {
                    "event": "Analyst Days 2025",
                    "topic": "Data-driven BA Transformation",
                    "speaker": "TBD",
                    "link": "https://example.com/analyst-days",
                    "notes": "Заполнить реальными данными из RSS/CSV.",
                    "collected_at": self.now.isoformat(),
                }
            ]
        else:
            entries = []
            for item in feed:
                record = {
                    "event": item.get("event"),
                    "topic": item.get("topic"),
                    "link": item.get("link"),
                    "date": item.get("date"),
                    "speaker": item.get("speaker"),
                    "collected_at": self.now.isoformat(),
                }
                # Optional date filtering
                if since and item.get("date"):
                    try:
                        event_date = datetime.fromisoformat(item["date"])
                        if event_date < since:
                            continue
                    except ValueError:
                        logger.debug("Invalid event date: %s", item["date"])
                entries.append(record)

        target_dir = ensure_output_dir(output_dir, self.name)
        output_file = self._write_output(target_dir, list(entries))
        metadata = {"feed_configured": bool(feed)}
        return CollectorResult(
            collector=self.name,
            status="ok",
            records_count=len(list(entries)),
            output_file=output_file,
            metadata=metadata,
        )

