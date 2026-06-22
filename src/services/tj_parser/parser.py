"""1C Technology Journal log parser.

Parses rphost .log files into structured TJEvent objects with
BSL source code correlation via Context field.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextFrame:
    """A single frame in the TJ Context call stack."""

    module: str  # e.g. "Документ.ПоступлениеТоваров.МодульОбъекта"
    line: int  # line number in BSL module
    code_fragment: str  # e.g. "Результат = Запрос.Выполнить()"


@dataclass
class TJEvent:
    """Parsed Technology Journal event."""

    timestamp: str  # HH:MM:SS.TTTTTT
    duration_us: int  # microseconds
    event_type: str  # SDBL, DBMSSQL, CALL, TLOCK, etc.
    process: str = ""
    user: str = ""
    context: list[ContextFrame] = field(default_factory=list)
    sql: str = ""
    sdbl: str = ""
    rows: int = 0
    rows_affected: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def top_context(self) -> Optional[ContextFrame]:
        """The innermost (most specific) context frame."""
        return self.context[-1] if self.context else None

    @property
    def call_stack(self) -> list[str]:
        """Human-readable call stack."""
        return [f"{f.module}:{f.line} → {f.code_fragment}" for f in self.context]


class TJParser:
    """Parser for 1C Technology Journal .log files.

    Usage:
        parser = TJParser()
        events = parser.parse_file("rphost_1234/26022200.log")
        slow = [e for e in events if e.duration_us > 1_000_000]
    """

    # Event line: HH:MM:SS.TTTTTT-D,EVENT,...
    RE_EVENT_START = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d+)-(\d+),(\w+),(.*)")
    RE_PROPERTY = re.compile(r"(\w+)='([^']*(?:''[^']*)*)'|(\w+)=([^,\s]+)")
    RE_CONTEXT_FRAME = re.compile(
        r"([А-Яа-яA-Za-z_]\w*(?:\.[А-Яа-яA-Za-z_]\w*)*)\s*:\s*(\d+)\s*:\s*(.+)"
    )

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Pick a decoder from the file's leading BOM.

        Real 1C Technology Journal logs on Windows are UTF-8 (frequently with a
        BOM) or UTF-16 LE/BE. A BOM left in the decoded text leaks into the first
        line, so RE_EVENT_START fails to match it and the first event block is
        silently dropped. ``utf-8-sig`` strips a UTF-8 BOM (and is a no-op on
        BOM-less UTF-8); the ``utf-16`` codec reads the BOM, auto-detects
        endianness, and strips it.
        """
        with open(path, "rb") as fb:
            head = fb.read(4)
        if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return "utf-16"
        return "utf-8-sig"

    def parse_file(
        self, path: str | Path, event_filter: set[str] | None = None
    ) -> list[TJEvent]:
        """Parse a single .log file.

        Args:
            path: Path to .log file
            event_filter: Only parse these event types (e.g. {"SDBL", "DBMSSQL", "TLOCK"})
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"TJ log not found: {path}")

        events = []
        current_lines: list[str] = []

        with open(
            path, "r", encoding=self._detect_encoding(path), errors="replace"
        ) as f:
            for line in f:
                if self.RE_EVENT_START.match(line):
                    if current_lines:
                        event = self._parse_event_block(current_lines, event_filter)
                        if event:
                            events.append(event)
                    current_lines = [line.rstrip()]
                else:
                    current_lines.append(line.rstrip())

        # Last event
        if current_lines:
            event = self._parse_event_block(current_lines, event_filter)
            if event:
                events.append(event)

        logger.info("Parsed %d events from %s", len(events), path.name)
        return events

    def parse_directory(
        self, dir_path: str | Path, event_filter: set[str] | None = None
    ) -> list[TJEvent]:
        """Parse all .log files in a directory (recursively)."""
        dir_path = Path(dir_path)
        all_events = []
        for log_file in sorted(dir_path.rglob("*.log")):
            events = self.parse_file(log_file, event_filter)
            all_events.extend(events)
        return all_events

    def _parse_event_block(
        self, lines: list[str], event_filter: set[str] | None
    ) -> Optional[TJEvent]:
        """Parse a multi-line event block into TJEvent."""
        full_text = "\n".join(lines)
        m = self.RE_EVENT_START.match(lines[0])
        if not m:
            return None

        timestamp = m.group(1)
        duration_us = int(m.group(2))
        event_type = m.group(3)

        if event_filter and event_type not in event_filter:
            return None

        # Parse properties
        props = {}
        for pm in self.RE_PROPERTY.finditer(full_text):
            if pm.group(1):
                props[pm.group(1)] = pm.group(2).replace("''", "'")
            elif pm.group(3):
                props[pm.group(3)] = pm.group(4)

        # Parse context frames
        context_frames = []
        raw_context = props.pop("Context", "")
        if raw_context:
            for ctx_line in raw_context.strip().split("\n"):
                ctx_line = ctx_line.strip()
                cm = self.RE_CONTEXT_FRAME.match(ctx_line)
                if cm:
                    context_frames.append(
                        ContextFrame(
                            module=cm.group(1),
                            line=int(cm.group(2)),
                            code_fragment=cm.group(3).strip(),
                        )
                    )

        return TJEvent(
            timestamp=timestamp,
            duration_us=duration_us,
            event_type=event_type,
            process=props.pop("p", ""),
            user=props.pop("Usr", ""),
            context=context_frames,
            sql=props.pop("Sql", ""),
            sdbl=props.pop("Sdbl", ""),
            rows=int(props.pop("Rows", 0)),
            rows_affected=int(props.pop("RowsAffected", 0)),
            extra=props,
        )
