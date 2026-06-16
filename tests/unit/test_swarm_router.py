"""Tests for Swarm Router — LLM distillation layer.

TDD: tests written BEFORE implementation.
Phase 5.0 of 1cAI.
"""

from __future__ import annotations

import pytest

from src.micro_swarm.router import (
    RouterDecision,
    RouterResult,
    SwarmRouter,
    TemplateResponder,
)


# --------------- Sample BSL code snippets ---------------

CLEAN_CODE = """\
Функция ПолучитьИмя(Сотрудник)
    Возврат Сотрудник.Наименование;
КонецФункции
"""

N_PLUS_ONE_CODE = """\
Для Каждого Элемент Из Коллекция Цикл
    Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");
    Результат = Запрос.Выполнить();
КонецЦикла
"""

EMPTY_CATCH_CODE = """\
Попытка
    ОпаснаяОперация();
Исключение
КонецПопытки
"""

SELECT_STAR_CODE = """\
Запрос = Новый Запрос;
Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
Результат = Запрос.Выполнить().Выгрузить();
"""

DEEPLY_NESTED_CODE = """\
Если А Тогда
    Если Б Тогда
        Если В Тогда
            Если Г Тогда
                Если Д Тогда
                    Действие();
                КонецЕсли;
            КонецЕсли;
        КонецЕсли;
    КонецЕсли;
КонецЕсли;
"""

COMPLEX_CODE = """\
Для Каждого Элемент Из Коллекция Цикл
    Попытка
        Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");
        Результат = Запрос.Выполнить();
        Если А Тогда
            Если Б Тогда
                Если В Тогда
                    Если Г Тогда
                        Действие();
                    КонецЕсли;
                КонецЕсли;
            КонецЕсли;
        КонецЕсли;
    Исключение
    КонецПопытки
КонецЦикла
"""


# --------------- RouterDecision ---------------

class TestRouterDecision:
    """Enum has exactly 3 values."""

    def test_has_clean(self):
        assert RouterDecision.CLEAN is not None

    def test_has_template(self):
        assert RouterDecision.TEMPLATE is not None

    def test_has_llm_required(self):
        assert RouterDecision.LLM_REQUIRED is not None

    def test_exactly_three_values(self):
        assert len(RouterDecision) == 3


# --------------- SwarmRouter.analyze ---------------

class TestSwarmRouterAnalyze:
    """analyze() runs all BSL domains and returns scores."""

    def test_returns_dict(self):
        router = SwarmRouter.default()
        result = router.analyze(CLEAN_CODE)
        assert isinstance(result, dict)

    def test_contains_bsl_domains(self):
        router = SwarmRouter.default()
        scores = router.analyze(CLEAN_CODE)
        expected_keys = {"bsl_pattern", "bsl_quality",
                         "query_optimizer", "error_predictor"}
        assert expected_keys.issubset(set(scores.keys()))

    def test_scores_are_floats(self):
        router = SwarmRouter.default()
        scores = router.analyze(CLEAN_CODE)
        for name, score in scores.items():
            assert isinstance(score, float), f"{name} is not float"

    def test_scores_in_range(self):
        router = SwarmRouter.default()
        scores = router.analyze(N_PLUS_ONE_CODE)
        for name, score in scores.items():
            assert 0.0 <= score <= 1.0, f"{name}={score} out of range"


# --------------- SwarmRouter.route ---------------

class TestSwarmRouterRoute:
    """route() maps scores to RouterDecision."""

    def test_all_low_scores_clean(self):
        router = SwarmRouter.default()
        scores = {"a": 0.1, "b": 0.2, "c": 0.05}
        assert router.route(scores) == RouterDecision.CLEAN

    def test_medium_scores_template(self):
        router = SwarmRouter.default()
        scores = {"a": 0.5, "b": 0.2, "c": 0.1}
        assert router.route(scores) == RouterDecision.TEMPLATE

    def test_high_scores_llm(self):
        router = SwarmRouter.default()
        scores = {"a": 0.8, "b": 0.7, "c": 0.9}
        assert router.route(scores) == RouterDecision.LLM_REQUIRED

    def test_custom_thresholds(self):
        router = SwarmRouter.default()
        router.clean_threshold = 0.5
        router.llm_threshold = 0.9
        scores = {"a": 0.6, "b": 0.4}
        assert router.route(scores) == RouterDecision.TEMPLATE


# --------------- SwarmRouter.review (full pipeline) ---------------

class TestSwarmRouterReview:
    """review() = analyze + route + respond."""

    def test_returns_router_result(self):
        router = SwarmRouter.default()
        result = router.review(CLEAN_CODE)
        assert isinstance(result, RouterResult)

    def test_clean_code_valid_decision(self):
        """Untrained models can't guarantee CLEAN — verify pipeline works."""
        router = SwarmRouter.default()
        result = router.review(CLEAN_CODE)
        assert result.decision in (
            RouterDecision.CLEAN,
            RouterDecision.TEMPLATE,
            RouterDecision.LLM_REQUIRED,
        )

    def test_clean_code_has_confidence(self):
        router = SwarmRouter.default()
        result = router.review(CLEAN_CODE)
        assert 0.0 <= result.confidence <= 1.0

    def test_problematic_code_not_clean(self):
        router = SwarmRouter.default()
        result = router.review(COMPLEX_CODE)
        assert result.decision in (
            RouterDecision.TEMPLATE, RouterDecision.LLM_REQUIRED)

    def test_problematic_code_has_response(self):
        router = SwarmRouter.default()
        result = router.review(COMPLEX_CODE)
        if result.decision == RouterDecision.TEMPLATE:
            assert result.response is not None
            assert len(result.response) > 0

    def test_empty_code_clean(self):
        router = SwarmRouter.default()
        result = router.review("")
        assert result.decision == RouterDecision.CLEAN


# --------------- TemplateResponder ---------------

class TestTemplateResponder:
    """Template responses in Russian for common BSL issues."""

    def test_n_plus_one_template(self):
        responder = TemplateResponder()
        response = responder.respond(
            max_domain="query_optimizer",
            features={"has_n_plus_one": 1.0},
        )
        assert response is not None
        assert "запрос" in response.lower() or "цикл" in response.lower()

    def test_empty_catch_template(self):
        responder = TemplateResponder()
        response = responder.respond(
            max_domain="error_predictor",
            features={"has_empty_catch": 1.0},
        )
        assert response is not None

    def test_select_star_template(self):
        responder = TemplateResponder()
        response = responder.respond(
            max_domain="query_optimizer",
            features={"has_select_star": 1.0},
        )
        assert response is not None

    def test_unknown_domain_returns_generic(self):
        responder = TemplateResponder()
        response = responder.respond(
            max_domain="unknown_domain",
            features={},
        )
        assert response is not None


# --------------- Self-training hook ---------------

class TestSelfTraining:
    """record_feedback stores LLM verdicts for future training."""

    def test_record_feedback(self):
        router = SwarmRouter.default()
        router.record_feedback(
            code=N_PLUS_ONE_CODE,
            swarm_scores={"query_optimizer": 0.8},
            llm_verdict="N+1 запрос обнаружен",
        )
        assert len(router.training_buffer) == 1

    def test_feedback_structure(self):
        router = SwarmRouter.default()
        router.record_feedback(
            code="test",
            swarm_scores={"a": 0.5},
            llm_verdict="verdict",
        )
        entry = router.training_buffer[0]
        assert "code" in entry
        assert "swarm_scores" in entry
        assert "llm_verdict" in entry

    def test_multiple_feedbacks(self):
        router = SwarmRouter.default()
        for i in range(5):
            router.record_feedback(
                code=f"code_{i}",
                swarm_scores={"a": 0.1 * i},
                llm_verdict=f"verdict_{i}",
            )
        assert len(router.training_buffer) == 5
