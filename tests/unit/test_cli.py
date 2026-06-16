"""Tests for CLI bsl-review command.

TDD RED: Tests written before implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.micro_swarm.cli import format_report, run_bsl_review


# --- format_report tests ---

class TestFormatReport:
    """Test Russian report formatting."""

    def test_empty_results_shows_no_files(self):
        report = format_report([])
        assert "0 файлов" in report

    def test_clean_file_shown_as_ok(self):
        results = [_make_result("module.bsl", "clean", loc=50)]
        report = format_report(results)
        assert "✅" in report
        assert "module.bsl" in report

    def test_template_file_shown_with_warning(self):
        results = [_make_result(
            "bad.bsl", "template", loc=100,
            response="⚠️ N+1 запрос",
        )]
        report = format_report(results)
        assert "⚠️" in report or "🔶" in report
        assert "bad.bsl" in report

    def test_llm_required_shown_as_critical(self):
        results = [_make_result("complex.bsl", "llm_required", loc=300)]
        report = format_report(results)
        assert "🔴" in report or "❌" in report
        assert "complex.bsl" in report

    def test_summary_stats_present(self):
        results = [
            _make_result("a.bsl", "clean", loc=10),
            _make_result("b.bsl", "template", loc=20),
            _make_result("c.bsl", "llm_required", loc=30),
        ]
        report = format_report(results)
        assert "3" in report  # total files
        assert "60" in report  # total LOC

    def test_llm_savings_percentage(self):
        results = [
            _make_result("a.bsl", "clean", loc=10),
            _make_result("b.bsl", "template", loc=20),
            _make_result("c.bsl", "llm_required", loc=30),
        ]
        report = format_report(results)
        # 2 out of 3 handled without LLM = 66.7%
        assert "66" in report or "67" in report


# --- run_bsl_review tests ---

class TestRunBslReview:
    """Test the main CLI entry point."""

    @patch("src.micro_swarm.cli.GoBridge")
    def test_returns_zero_on_success(self, mock_bridge_cls):
        bridge = MagicMock()
        bridge.scan_and_review.return_value = [
            _make_result("ok.bsl", "clean", loc=10),
        ]
        mock_bridge_cls.return_value = bridge

        exit_code = run_bsl_review("/fake/path")
        assert exit_code == 0

    @patch("src.micro_swarm.cli.GoBridge")
    def test_returns_one_when_llm_required(self, mock_bridge_cls):
        bridge = MagicMock()
        bridge.scan_and_review.return_value = [
            _make_result("bad.bsl", "llm_required", loc=100),
        ]
        mock_bridge_cls.return_value = bridge

        exit_code = run_bsl_review("/fake/path")
        assert exit_code == 1

    @patch("src.micro_swarm.cli.GoBridge")
    def test_prints_report_to_stdout(self, mock_bridge_cls, capsys):
        bridge = MagicMock()
        bridge.scan_and_review.return_value = [
            _make_result("test.bsl", "template", loc=50,
                         response="⚠️ Тест"),
        ]
        mock_bridge_cls.return_value = bridge

        run_bsl_review("/fake/path")
        captured = capsys.readouterr()
        assert "test.bsl" in captured.out

    @patch("src.micro_swarm.cli.GoBridge")
    def test_handles_scan_error(self, mock_bridge_cls):
        bridge = MagicMock()
        bridge.scan_and_review.side_effect = FileNotFoundError("no binary")
        mock_bridge_cls.return_value = bridge

        exit_code = run_bsl_review("/fake/path")
        assert exit_code == 2  # error exit code


# --- helpers ---

def _make_result(path: str, decision: str, loc: int = 0,
                 response: str | None = None):
    """Create a BridgeResult-like object for testing."""
    from src.micro_swarm.go_bridge import BridgeResult
    return BridgeResult(
        path=path,
        loc=loc,
        decision=decision,
        response=response,
        confidence=0.8,
        scores={"query_optimizer": 0.5},
        go_features={"has_n_plus_one": 1.0},
    )
