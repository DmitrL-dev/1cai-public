
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Type

from scripts.ba_pipeline.base import BaseCollector, CollectorResult
from scripts.ba_pipeline.collectors import (ConferenceCollector,
                                            InternalUsageCollector,
                                            JobMarketCollector,
                                            RegulationCollector)
from scripts.ba_pipeline.utils import figure_output_dir, setup_logging

logger = logging.getLogger("ba_pipeline.orchestrator")

COLLECTOR_CLASSES: Tuple[Type[BaseCollector], ...] = (
    JobMarketCollector,
    ConferenceCollector,
    RegulationCollector,
    InternalUsageCollector,
)


def available_collectors() -> Dict[str, Type[BaseCollector]]:
    return {cls.name: cls for cls in COLLECTOR_CLASSES}


def instantiate_collectors(selected: Optional[Sequence[str]] = None) -> List[BaseCollector]:
    registry = available_collectors()
    if selected:
        missing = [name for name in selected if name not in registry]
        if missing:
            raise ValueError(f"Unknown collectors requested: {missing}")
        names = list(dict.fromkeys(selected))
    else:
        names = list(registry.keys())
    collectors: List[BaseCollector] = [registry[name]() for name in names]
    return collectors


def run_pipeline(
    *,
    output_dir: Optional[Path] = None,
    collector_names: Optional[Sequence[str]] = None,
    since: Optional[datetime] = None,
) -> Dict[str, List[Dict[str, object]]]:
    target_dir = figure_output_dir(str(output_dir) if output_dir else None)
    collectors = instantiate_collectors(collector_names)

    logger.info("Starting BA pipeline with %d collectors -> %s", len(collectors), target_dir)
    results: List[CollectorResult] = []
    for collector in collectors:
        logger.info("Running collector: %s", collector.name)
        try:
            result = collector.collect(output_dir=target_dir, since=since)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Collector %s failed: %s", collector.name, exc)
            result = CollectorResult(collector=collector.name, status="error", metadata={"error": str(exc)})
        results.append(result)
        logger.info(
            "%s -> status=%s, records=%s",
            result.collector,
            result.status,
            result.records_count,
        )

    return {
        "output_dir": str(target_dir),
        "collectors": [r.to_dict() for r in results],
    }


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BA data pipeline orchestrator")
    parser.add_argument("--output-dir", help="Каталог для выгрузки (по умолчанию data/ba_intel)")
    parser.add_argument(
        "--collectors",
        nargs="+",
        help="Ограничить список коллекторов (job_market, conference_digest, regulation_watcher, internal_usage)",
    )
    parser.add_argument("--since-days", type=int, help="Собрать только данные за последние X дней")
    parser.add_argument("--verbose", action="store_true", help="Расширенный лог")
    return parser.parse_args(args=args)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    setup_logging(verbose=args.verbose)
    since = BaseCollector.parse_since(args.since_days)
    summary = run_pipeline(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        collector_names=args.collectors,
        since=since,
    )
    logger.info("Pipeline completed: %s", summary)


if __name__ == "__main__":  # pragma: no cover
    main()

