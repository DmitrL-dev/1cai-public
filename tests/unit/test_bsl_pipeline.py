"""Tests for BSL Analysis Pipeline.

Covers all three decision flows, Go bridge fallback, and PipelineResult model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ai.bsl_pipeline import BSLPipeline, PipelineResult, run_pipeline


# ── Helpers ───────────────────────────────────────────────────────

CLEAN_BSL = """\
Функция ПолучитьИмя(Сотрудник)
    Возврат Сотрудник.Наименование;
КонецФункции
"""

TEMPLATE_BSL = """\
Для Каждого Элемент Из Коллекция Цикл
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
    Результат = Запрос.Выполнить();
КонецЦикла
"""


def _make_pipeline(tmp_path: Path, files: dict[str, str]) -> BSLPipeline:
    """Create pipeline with Go bridge disabled and BSL files on disk."""
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    with patch("src.ai.bsl_pipeline.BSLPipeline._init_go_bridge"):
        pipe = BSLPipeline(str(tmp_path))
        pipe._go_bridge = None  # force Python path
        pipe.router = MagicMock()
    return pipe


# ── PipelineResult model ─────────────────────────────────────────


class TestPipelineResult:
    def test_defaults(self):
        r = PipelineResult(file_path="a.bsl", decision="clean")
        assert r.response is None
        assert r.scores == {}
        assert r.llm_model is None

    def test_all_fields(self):
        r = PipelineResult(
            file_path="b.bsl",
            decision="template",
            response="⚠️ N+1",
            scores={"query_optimizer": 0.5},
            llm_model="qwen-72b",
        )
        assert r.decision == "template"
        assert r.llm_model == "qwen-72b"
        assert "query_optimizer" in r.scores


# ── CLEAN decision flow ──────────────────────────────────────────


class TestCleanFlow:
    def test_clean_file_returns_clean_result(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        pipe = _make_pipeline(tmp_path, {"module.bsl": CLEAN_BSL})
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.CLEAN,
            scores={"bsl_quality": 0.1},
            response=None,
            confidence=0.9,
        )

        results = pipe.run()

        assert len(results) == 1
        assert results[0].decision == "clean"
        assert results[0].response is None
        assert results[0].llm_model is None


# ── TEMPLATE decision flow ───────────────────────────────────────


class TestTemplateFlow:
    def test_template_file_returns_response(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        pipe = _make_pipeline(tmp_path, {"bad.bsl": TEMPLATE_BSL})
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.TEMPLATE,
            scores={"query_optimizer": 0.5},
            response="⚠️ N+1 запрос в цикле",
            confidence=0.5,
        )

        results = pipe.run()

        assert len(results) == 1
        assert results[0].decision == "template"
        assert results[0].response is not None
        assert "N+1" in results[0].response


# ── LLM_REQUIRED stub flow ───────────────────────────────────────


class TestLLMRequiredFlow:
    def test_llm_required_without_provider(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        pipe = _make_pipeline(tmp_path, {"complex.bsl": CLEAN_BSL})
        pipe.llm_provider = None
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.LLM_REQUIRED,
            scores={"bsl_quality": 0.9},
            response=None,
            confidence=0.9,
        )

        results = pipe.run()

        assert len(results) == 1
        assert results[0].decision == "llm_required"
        assert results[0].llm_model is None
        pipe.router.record_feedback.assert_called_once()

    def test_llm_required_with_provider(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        provider = MagicMock()
        provider.review.return_value = "LLM says: refactor this"
        provider.model_name = "test-llm"

        pipe = _make_pipeline(tmp_path, {"complex.bsl": CLEAN_BSL})
        pipe.llm_provider = provider
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.LLM_REQUIRED,
            scores={"bsl_quality": 0.9},
            response=None,
            confidence=0.9,
        )

        results = pipe.run()

        assert results[0].decision == "llm_required"
        assert results[0].response == "LLM says: refactor this"
        assert results[0].llm_model == "test-llm"


# ── Go bridge fallback ───────────────────────────────────────────


class TestGoBridgeFallback:
    def test_falls_back_to_python_when_go_unavailable(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        pipe = _make_pipeline(tmp_path, {"m.bsl": CLEAN_BSL})
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.CLEAN,
            scores={},
            confidence=1.0,
        )

        # Go bridge is None → must use Python path
        assert pipe._go_bridge is None
        results = pipe.run()
        assert len(results) == 1
        pipe.router.review.assert_called_once()

    def test_falls_back_when_go_raises(self, tmp_path):
        from src.micro_swarm.router import RouterDecision, RouterResult

        pipe = _make_pipeline(tmp_path, {"m.bsl": CLEAN_BSL})
        pipe._go_bridge = MagicMock()
        pipe._go_bridge.scan_and_review.side_effect = RuntimeError("go failed")
        pipe.router.review.return_value = RouterResult(
            decision=RouterDecision.CLEAN,
            scores={},
            confidence=1.0,
        )

        results = pipe.run()
        assert len(results) == 1
        assert results[0].decision == "clean"


# ── Convenience function ─────────────────────────────────────────


class TestRunPipeline:
    @patch("src.ai.bsl_pipeline.BSLPipeline")
    def test_run_pipeline_convenience(self, mock_cls):
        mock_cls.return_value.run.return_value = [
            PipelineResult(file_path="x.bsl", decision="clean"),
        ]
        results = run_pipeline("/fake")
        assert len(results) == 1
        mock_cls.assert_called_once_with("/fake")
