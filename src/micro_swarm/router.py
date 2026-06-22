"""Swarm Router — LLM distillation layer for BSL code analysis.

Routes BSL code through Micro-Model Swarm and decides:
  CLEAN        → code is fine, no LLM needed
  TEMPLATE     → known issue, respond with Russian template
  LLM_REQUIRED → complex case, forward to LLM agent

Architecture:
  code → SwarmRouter.analyze() → scores
       → SwarmRouter.route()   → decision
       → TemplateResponder     → text (if TEMPLATE)

Self-training:
  record_feedback(code, swarm_scores, llm_verdict) stores pairs
  for future model training (LLM teaches Swarm).

Phase 5.0 of 1cAI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RouterDecision(str, Enum):
    """Routing decision for BSL code."""

    CLEAN = "clean"
    TEMPLATE = "template"
    LLM_REQUIRED = "llm_required"


@dataclass
class RouterResult:
    """Result of SwarmRouter.review()."""

    decision: RouterDecision
    scores: dict[str, float]
    response: str | None = None
    confidence: float = 0.0


class TemplateResponder:
    """Generate Russian template responses for common BSL issues.

    No LLM needed — pure rule-based responses for known patterns.
    """

    # domain → feature → template
    _TEMPLATES: dict[str, dict[str, str]] = {
        "query_optimizer": {
            "has_n_plus_one": (
                "⚠️ Обнаружен N+1 запрос: запрос выполняется внутри цикла. "
                "Рекомендация: вынесите запрос за пределы цикла и используйте "
                "СОЕДИНЕНИЕ или временную таблицу для пакетной обработки."
            ),
            "has_select_star": (
                "⚠️ Используется ВЫБРАТЬ * — выбираются все поля таблицы. "
                "Рекомендация: укажите только необходимые поля для снижения "
                "нагрузки на СУБД и сеть."
            ),
            "has_no_index_hint": (
                "💡 Запрос может работать без индекса. "
                "Рекомендация: проверьте план запроса и добавьте "
                "индекс по полям условия отбора."
            ),
            "has_unnecessary_join": (
                "💡 Обнаружено избыточное СОЕДИНЕНИЕ. "
                "Проверьте, используются ли все соединённые таблицы в результате."
            ),
            "has_subquery_in_condition": (
                "⚠️ Подзапрос в условии WHERE может снижать производительность. "
                "Рекомендация: замените на СОЕДИНЕНИЕ или временную таблицу."
            ),
        },
        "error_predictor": {
            "has_empty_catch": (
                "🔴 Пустой блок Исключение — ошибки проглатываются. "
                "Рекомендация: добавьте логирование или обработку ошибки: "
                'ЗаписьЖурналаРегистрации("Ошибка", ОписаниеОшибки()).'
            ),
            "has_division_risk": (
                "⚠️ Возможное деление на ноль. "
                "Рекомендация: добавьте проверку делителя перед операцией."
            ),
            "has_magic_numbers": (
                "💡 Обнаружены магические числа в коде. "
                "Рекомендация: вынесите в именованные константы для читаемости."
            ),
            "has_deep_nesting": (
                "⚠️ Глубокая вложенность условий (>4 уровня). "
                "Рекомендация: используйте ранний выход (Возврат/Продолжить) "
                "или выделите логику в отдельные функции."
            ),
        },
        "bsl_quality": {
            "high_complexity": (
                "⚠️ Высокая цикломатическая сложность. "
                "Рекомендация: декомпозируйте функцию на более мелкие части."
            ),
        },
        "bsl_pattern": {},
    }

    _GENERIC = "ℹ️ Обнаружены потенциальные проблемы в коде. Рекомендуется ревью."

    def respond(
        self,
        max_domain: str,
        features: dict[str, float],
    ) -> str:
        """Generate template response based on detected issues.

        Args:
            max_domain: domain with the highest score
            features: extracted features dict

        Returns:
            Russian-language response string
        """
        domain_templates = self._TEMPLATES.get(max_domain, {})

        # Find first matching feature
        responses: list[str] = []
        for feature_name, value in features.items():
            if value >= 1.0 and feature_name in domain_templates:
                responses.append(domain_templates[feature_name])

        if responses:
            return "\n\n".join(responses)

        return self._GENERIC


class SwarmRouter:
    """Routes BSL code through Micro-Model Swarm.

    Runs all BSL domains, aggregates scores, decides whether to
    use a template response or escalate to LLM.

    Usage:
        router = SwarmRouter.default()
        result = router.review(bsl_code)
        if result.decision == RouterDecision.TEMPLATE:
            print(result.response)
    """

    def __init__(
        self,
        domains: list[tuple[Any, Any]] | None = None,
        clean_threshold: float = 0.3,
        llm_threshold: float = 0.7,
    ) -> None:
        self.domains = domains or []
        self.clean_threshold = clean_threshold
        self.llm_threshold = llm_threshold
        self.training_buffer: list[dict[str, Any]] = []
        self._responder = TemplateResponder()

    @classmethod
    def default(cls) -> SwarmRouter:
        """Create router with all BSL domains."""
        from src.micro_swarm.bsl_domains import (
            BSL_PATTERN_DOMAIN,
            BSL_QUALITY_DOMAIN,
            ERROR_PREDICTOR_DOMAIN,
            QUERY_OPTIMIZER_DOMAIN,
            extract_bsl_pattern_features,
            extract_bsl_quality_features,
            extract_error_features,
            extract_query_optimizer_features,
        )
        from src.micro_swarm.model import MicroModel, MicroModelConfig

        domains = [
            ("bsl_pattern", BSL_PATTERN_DOMAIN, extract_bsl_pattern_features),
            ("bsl_quality", BSL_QUALITY_DOMAIN, extract_bsl_quality_features),
            (
                "query_optimizer",
                QUERY_OPTIMIZER_DOMAIN,
                extract_query_optimizer_features,
            ),
            ("error_predictor", ERROR_PREDICTOR_DOMAIN, extract_error_features),
        ]

        initialized: list[tuple[str, Any, Any, MicroModel]] = []
        weights_dir = Path("data/models")
        loaded = 0
        for name, domain, extractor in domains:
            config = MicroModelConfig(n_features=domain.n_features)
            weight_path = weights_dir / f"{name}.json"
            if weight_path.exists():
                model = MicroModel.load(str(weight_path))
                loaded += 1
            else:
                model = MicroModel(config)
            initialized.append((name, domain, extractor, model))

        if loaded:
            import logging

            logging.getLogger(__name__).info(
                "Loaded %d/%d pre-trained weights from %s",
                loaded,
                len(domains),
                weights_dir,
            )

        router = cls(domains=initialized)
        return router

    def analyze(self, code: str) -> dict[str, float]:
        """Run all BSL domains on code, return scores.

        Args:
            code: BSL source code string

        Returns:
            Dict mapping domain name to score (0.0 - 1.0)
        """
        scores: dict[str, float] = {}

        for name, domain, extractor, model in self.domains:
            raw_features = extractor(code)
            normalized = domain.extract(raw_features)
            score, _ = model.forward(normalized)
            scores[name] = score

        return scores

    def route(self, scores: dict[str, float]) -> RouterDecision:
        """Decide routing based on aggregated scores.

        Logic:
            max(scores) < clean_threshold  → CLEAN
            max(scores) >= llm_threshold   → LLM_REQUIRED
            otherwise                      → TEMPLATE

        Args:
            scores: domain name → score mapping

        Returns:
            RouterDecision enum value
        """
        if not scores:
            return RouterDecision.CLEAN

        max_score = max(scores.values())

        if max_score < self.clean_threshold:
            return RouterDecision.CLEAN
        elif max_score >= self.llm_threshold:
            return RouterDecision.LLM_REQUIRED
        else:
            return RouterDecision.TEMPLATE

    def review(self, code: str) -> RouterResult:
        """Full pipeline: analyze → route → respond.

        Args:
            code: BSL source code string

        Returns:
            RouterResult with decision, scores, response, confidence
        """
        if not code or not code.strip():
            return RouterResult(
                decision=RouterDecision.CLEAN,
                scores={},
                response=None,
                confidence=1.0,
            )

        scores = self.analyze(code)
        decision = self.route(scores)

        response = None
        if decision == RouterDecision.TEMPLATE:
            # Find domain with highest score for template selection
            max_domain = max(scores, key=scores.get)  # type: ignore[arg-type]
            # Get raw features for template matching
            for name, domain, extractor, model in self.domains:
                if name == max_domain:
                    raw_features = extractor(code)
                    response = self._responder.respond(max_domain, raw_features)
                    break

        # Confidence = how certain we are about the decision
        max_score = max(scores.values()) if scores else 0.0
        if decision == RouterDecision.CLEAN:
            confidence = 1.0 - max_score  # lower scores = more confident
        elif decision == RouterDecision.LLM_REQUIRED:
            confidence = max_score  # higher scores = more confident
        else:
            confidence = 0.5  # template zone = uncertain

        return RouterResult(
            decision=decision,
            scores=scores,
            response=response,
            confidence=confidence,
        )

    def review_from_features(
        self,
        features: dict[str, float],
    ) -> RouterResult:
        """Review using pre-extracted features (from Go scanner).

        Skips Python extraction — Go already did the heavy lifting.
        Maps Go feature keys to domain scores by aggregating per-domain.

        Args:
            features: dict from Go bsl-scan (e.g. has_n_plus_one: 1.0)

        Returns:
            RouterResult with decision, scores, response, confidence
        """
        # Map Go features to domain scores
        domain_features: dict[str, list[str]] = {
            "query_optimizer": [
                "has_n_plus_one",
                "has_select_star",
                "has_no_index_hint",
                "has_unnecessary_join",
                "has_subquery_in_condition",
            ],
            "error_predictor": [
                "has_empty_catch",
                "has_division_risk",
                "has_magic_numbers",
                "has_deep_nesting",
            ],
            "bsl_pattern": [
                "has_form_handler",
                "has_db_query",
                "has_print_form",
                "has_http_call",
                "has_scheduled_job",
            ],
            "bsl_quality": [
                "complexity",
                "doc_coverage",
                "max_nesting",
                "loc",
            ],
        }

        scores: dict[str, float] = {}
        for domain, keys in domain_features.items():
            domain_vals = [features.get(k, 0.0) for k in keys]
            # Cap each value at 1.0 (binary flags), compute mean, then
            # apply sqrt to amplify single-issue signal into TEMPLATE zone.
            # 1/5 flags → √0.2 = 0.45 (TEMPLATE), 3/5 → √0.6 = 0.77 (LLM)
            capped = [min(v, 1.0) for v in domain_vals]
            raw_mean = sum(capped) / max(len(capped), 1)
            scores[domain] = min(raw_mean**0.5, 1.0)

        decision = self.route(scores)

        response = None
        if decision == RouterDecision.TEMPLATE:
            max_domain = max(scores, key=scores.get)  # type: ignore[arg-type]
            response = self._responder.respond(max_domain, features)

        max_score = max(scores.values()) if scores else 0.0
        if decision == RouterDecision.CLEAN:
            confidence = 1.0 - max_score
        elif decision == RouterDecision.LLM_REQUIRED:
            confidence = max_score
        else:
            confidence = 0.5

        return RouterResult(
            decision=decision,
            scores=scores,
            response=response,
            confidence=confidence,
        )

    def record_feedback(
        self,
        code: str,
        swarm_scores: dict[str, float],
        llm_verdict: str,
    ) -> None:
        """Record LLM feedback for future self-training.

        Each entry becomes a training sample: the LLM teaches the Swarm.

        Args:
            code: original BSL code
            swarm_scores: what the Swarm predicted
            llm_verdict: what the LLM said
        """
        self.training_buffer.append(
            {
                "code": code,
                "swarm_scores": swarm_scores,
                "llm_verdict": llm_verdict,
            }
        )
