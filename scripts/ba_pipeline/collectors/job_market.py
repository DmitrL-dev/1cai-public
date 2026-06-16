
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from scripts.ba_pipeline.base import (BaseCollector, CollectorResult,
                                      ensure_output_dir)
from scripts.ba_pipeline.utils import load_json_env

logger = logging.getLogger(__name__)


class JobMarketCollector(BaseCollector):
    """Collect job market snapshots from configured sources.

    For the first implementation we rely on environment JSON payload
    (`BA_MARKET_SOURCES`) with pre-collected entries to avoid flaky HTTP calls.
    """

    name = "job_market"
    description = "Снимок вакансий (hh.ru, LinkedIn, etc.)"

    SOURCE_ENV = "BA_MARKET_SOURCES"

    def collect(
        self,
        *,
        output_dir: Path,
        since: Optional[datetime],
    ) -> CollectorResult:
        sources = list(load_json_env(self.SOURCE_ENV))
        if not sources:
            logger.info("No sources configured for job market collector; creating stub snapshot.")
            payload: Iterable[Dict[str, Any]] = [
                {
                    "platform": "stub",
                    "title": "Business Analyst (1C, Data Foundation)",
                    "location": "Remote",
                    "skills": ["1C", "SQL", "Power BI", "BABOK"],
                    "level": "Senior",
                    "collected_at": self.now.isoformat(),
                    "note": "Configure BA_MARKET_SOURCES to replace stub data.",
                }
            ]
        else:
            payload = []
            for item in sources:
                record = {
                    "platform": item.get("platform", "unknown"),
                    "title": item.get("title"),
                    "location": item.get("location"),
                    "skills": item.get("skills", []),
                    "level": item.get("level"),
                    "posted_at": item.get("posted_at"),
                    "collected_at": self.now.isoformat(),
                }
                if since and item.get("posted_at"):
                    try:
                        posted = datetime.fromisoformat(item["posted_at"])
                        if posted < since:
                            continue
                    except ValueError:
                        logger.debug("Invalid posted_at in %s", item)
                payload.append(record)

        target_dir = ensure_output_dir(output_dir, self.name)
        output_file = self._write_output(target_dir, list(payload))
        metadata = {"sources_configured": bool(sources)}
        return CollectorResult(
            collector=self.name,
            status="ok",
            records_count=len(list(payload)),
            output_file=output_file,
            metadata=metadata,
        )

