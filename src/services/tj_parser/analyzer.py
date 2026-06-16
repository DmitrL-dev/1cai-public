"""TJ Performance Analyzer (Перформер).

Correlates Technology Journal events with BSL source code
to identify performance bottlenecks.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .parser import TJEvent, TJParser

logger = logging.getLogger(__name__)


@dataclass
class QueryHotspot:
    """A frequently executed or slow query linked to BSL source."""

    module: str
    line: int
    code_fragment: str
    sdbl: str
    total_calls: int = 0
    total_duration_us: int = 0
    max_duration_us: int = 0
    avg_rows: float = 0.0
    is_in_loop: bool = False  # True if N+1 pattern detected

    @property
    def avg_duration_ms(self) -> float:
        return (self.total_duration_us / max(self.total_calls, 1)) / 1000

    @property
    def total_duration_ms(self) -> float:
        return self.total_duration_us / 1000


@dataclass
class PerformanceReport:
    """Performance analysis report."""

    total_events: int = 0
    total_duration_ms: float = 0.0
    hotspots: list[QueryHotspot] = field(default_factory=list)
    n_plus_one: list[QueryHotspot] = field(default_factory=list)
    lock_waits: list[dict] = field(default_factory=list)
    deadlocks: list[dict] = field(default_factory=list)


class TJPerformanceAnalyzer:
    """Analyzes Technology Journal for performance bottlenecks.

    Usage:
        analyzer = TJPerformanceAnalyzer()
        report = analyzer.analyze("./tj_logs/")

        for h in report.hotspots[:10]:
            print(f"{h.module}:{h.line} — {h.total_calls}x, "
                  f"avg {h.avg_duration_ms:.1f}ms: {h.code_fragment}")
    """

    def __init__(self, min_duration_ms: float = 100.0, n_plus_one_threshold: int = 5):
        self.min_duration_ms = min_duration_ms
        self.n_plus_one_threshold = n_plus_one_threshold
        self.parser = TJParser()

    def analyze(self, log_path: str, top_n: int = 20) -> PerformanceReport:
        """Analyze TJ logs and produce performance report."""
        from pathlib import Path

        path = Path(log_path)
        event_filter = {
            "SDBL",
            "DBMSSQL",
            "DBPOSTGRS",
            "TLOCK",
            "TTIMEOUT",
            "TDEADLOCK",
        }
        events = (
            self.parser.parse_file(path, event_filter=event_filter)
            if path.is_file()
            else self.parser.parse_directory(path, event_filter=event_filter)
        )

        report = PerformanceReport(total_events=len(events))

        # Group query events by source location
        query_groups: dict[str, list[TJEvent]] = defaultdict(list)
        for event in events:
            if event.event_type in ("SDBL", "DBMSSQL", "DBPOSTGRS"):
                report.total_duration_ms += event.duration_us / 1000
                ctx = event.top_context
                if ctx:
                    key = f"{ctx.module}:{ctx.line}"
                    query_groups[key].append(event)

            elif event.event_type == "TLOCK":
                report.lock_waits.append(
                    {
                        "timestamp": event.timestamp,
                        "duration_ms": event.duration_us / 1000,
                        "context": event.call_stack,
                        "user": event.user,
                    }
                )
            elif event.event_type == "TDEADLOCK":
                report.deadlocks.append(
                    {
                        "timestamp": event.timestamp,
                        "context": event.call_stack,
                        "user": event.user,
                    }
                )

        # Build hotspots
        for key, group_events in query_groups.items():
            ctx = group_events[0].top_context
            if not ctx:
                continue

            total_dur = sum(e.duration_us for e in group_events)
            total_rows = sum(e.rows for e in group_events)
            max_dur = max(e.duration_us for e in group_events)
            sdbl = group_events[0].sdbl or group_events[0].sql

            hotspot = QueryHotspot(
                module=ctx.module,
                line=ctx.line,
                code_fragment=ctx.code_fragment,
                sdbl=sdbl[:500],
                total_calls=len(group_events),
                total_duration_us=total_dur,
                max_duration_us=max_dur,
                avg_rows=total_rows / len(group_events) if group_events else 0,
                is_in_loop=len(group_events) >= self.n_plus_one_threshold,
            )

            if hotspot.is_in_loop:
                report.n_plus_one.append(hotspot)

            if total_dur / 1000 >= self.min_duration_ms:
                report.hotspots.append(hotspot)

        # Sort by total duration (worst first)
        report.hotspots.sort(key=lambda h: h.total_duration_us, reverse=True)
        report.n_plus_one.sort(key=lambda h: h.total_calls, reverse=True)
        report.hotspots = report.hotspots[:top_n]

        logger.info(
            "Analysis: %d events, %d hotspots, %d N+1 patterns, %d locks, %d deadlocks",
            report.total_events,
            len(report.hotspots),
            len(report.n_plus_one),
            len(report.lock_waits),
            len(report.deadlocks),
        )
        return report
