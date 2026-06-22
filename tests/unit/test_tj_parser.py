"""Tests for TJ Parser (Перформер)."""

from pathlib import Path

import pytest

from src.services.tj_parser.analyzer import TJPerformanceAnalyzer
from src.services.tj_parser.parser import ContextFrame, TJEvent, TJParser

# === TJ Log Fixtures ===

TJ_LOG_SIMPLE = """12:45:03.456789-3000000,SDBL,p:1:1:1,Usr=Админ,Context='Документ.ПоступлениеТоваров.МодульОбъекта : 145 : Результат = Запрос.Выполнить()',Sql='SELECT T1.Name FROM Document123 T1',Sdbl='ВЫБРАТЬ Наименование ИЗ Документ.ПоступлениеТоваров',Rows=500
12:45:04.123456-50000,SDBL,p:1:1:1,Usr=Админ,Context='ОбщийМодуль.ОбщегоНазначения.Модуль : 89 : ВыполнитьЗапрос()',Sql='SELECT 1',Sdbl='ВЫБРАТЬ 1',Rows=1
12:45:05.000000-100000,TLOCK,p:1:1:1,Usr=Админ,Context='Документ.ПоступлениеТоваров.МодульОбъекта : 200 : Движения.Записать()'
12:45:06.000000-0,TDEADLOCK,p:1:1:1,Usr=Админ,Context='Документ.X.МодульОбъекта : 10 : Записать()'
"""

TJ_LOG_N_PLUS_ONE = "\n".join(
    [
        f"12:45:0{i}.000000-10000,SDBL,p:1:1:1,Usr=Админ,Context='Документ.X.МодульОбъекта : 50 : Запрос.Выполнить()',Sdbl='ВЫБРАТЬ * ИЗ Справочник.Y',Rows=1"
        for i in range(10)
    ]
)


@pytest.fixture
def parser():
    return TJParser()


@pytest.fixture
def simple_log(tmp_path):
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(TJ_LOG_SIMPLE, encoding="utf-8")
    return log_file


@pytest.fixture
def n_plus_one_log(tmp_path):
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(TJ_LOG_N_PLUS_ONE, encoding="utf-8")
    return log_file


@pytest.fixture
def bom_log(tmp_path):
    """simple_log written WITH a UTF-8 BOM — real rphost logs commonly have one."""
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(TJ_LOG_SIMPLE.encode("utf-8-sig"))
    return log_file


@pytest.fixture
def utf16_log(tmp_path):
    """simple_log as UTF-16 (LE BOM) — a common 1C TJ encoding on Windows."""
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(TJ_LOG_SIMPLE.encode("utf-16"))
    return log_file


class TestTJParser:
    """Test TJ log parsing."""

    def test_parse_basic_events(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        assert len(events) == 4

    def test_event_types(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        types = [e.event_type for e in events]
        assert "SDBL" in types
        assert "TLOCK" in types
        assert "TDEADLOCK" in types

    def test_event_filter(self, parser, simple_log):
        events = parser.parse_file(simple_log, event_filter={"SDBL"})
        assert all(e.event_type == "SDBL" for e in events)

    def test_duration_parsing(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        sdbl = [e for e in events if e.event_type == "SDBL"][0]
        assert sdbl.duration_us == 3000000  # 3 seconds

    def test_context_parsing(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        sdbl = [e for e in events if e.event_type == "SDBL"][0]
        ctx = sdbl.top_context
        assert ctx is not None
        assert ctx.module == "Документ.ПоступлениеТоваров.МодульОбъекта"
        assert ctx.line == 145

    def test_sdbl_extraction(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        sdbl = [e for e in events if e.event_type == "SDBL"][0]
        assert "Наименование" in sdbl.sdbl

    def test_rows_parsing(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        sdbl = [e for e in events if e.event_type == "SDBL"][0]
        assert sdbl.rows == 500

    def test_parse_directory(self, parser, simple_log):
        events = parser.parse_directory(simple_log.parent.parent)
        assert len(events) == 4

    def test_call_stack_property(self, parser, simple_log):
        events = parser.parse_file(simple_log)
        sdbl = [e for e in events if e.event_type == "SDBL"][0]
        stack = sdbl.call_stack
        assert len(stack) >= 1
        assert "145" in stack[0]


class TestTJAnalyzer:
    """Test performance analysis."""

    def test_hotspot_detection(self, simple_log):
        analyzer = TJPerformanceAnalyzer(min_duration_ms=1.0)
        report = analyzer.analyze(str(simple_log.parent.parent))
        assert report.total_events > 0

    def test_n_plus_one_detection(self, n_plus_one_log):
        analyzer = TJPerformanceAnalyzer(min_duration_ms=0.1, n_plus_one_threshold=5)
        report = analyzer.analyze(str(n_plus_one_log.parent.parent))
        assert len(report.n_plus_one) >= 1
        assert report.n_plus_one[0].is_in_loop is True
        assert report.n_plus_one[0].total_calls >= 5

    def test_lock_tracking(self, simple_log):
        analyzer = TJPerformanceAnalyzer(min_duration_ms=0.1)
        report = analyzer.analyze(str(simple_log.parent.parent))
        assert len(report.lock_waits) >= 1

    def test_deadlock_tracking(self, simple_log):
        analyzer = TJPerformanceAnalyzer(min_duration_ms=0.1)
        report = analyzer.analyze(str(simple_log.parent.parent))
        assert len(report.deadlocks) >= 1


class TestTJEncoding:
    """Regression: a leading BOM must not drop the first event (utf-8-sig / utf-16)."""

    def test_bom_keeps_first_event(self, parser, bom_log):
        events = parser.parse_file(bom_log)
        # Without the fix the BOM breaks RE_EVENT_START on line 0 and the first
        # SDBL block is dropped -> 3 events. With it, all 4 survive.
        assert len(events) == 4
        first = events[0]
        assert first.event_type == "SDBL"
        assert first.duration_us == 3000000
        assert first.top_context is not None
        assert first.top_context.module == "Документ.ПоступлениеТоваров.МодульОбъекта"
        assert first.top_context.line == 145

    def test_bom_hotspot_survives(self, bom_log):
        report = TJPerformanceAnalyzer(min_duration_ms=1.0).analyze(
            str(bom_log.parent.parent)
        )
        assert report.total_events == 4
        assert len(report.hotspots) >= 1
        top = report.hotspots[0]
        assert top.module == "Документ.ПоступлениеТоваров.МодульОбъекта"
        assert top.line == 145
        assert round(top.total_duration_ms) == 3000

    def test_utf16_keeps_first_event(self, parser, utf16_log):
        events = parser.parse_file(utf16_log)
        assert len(events) == 4
        assert events[0].event_type == "SDBL"
        assert events[0].duration_us == 3000000
        assert events[0].top_context.line == 145
