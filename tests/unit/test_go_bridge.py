"""Tests for Go Bridge and review_from_features integration."""

import pytest

from src.micro_swarm.router import RouterDecision, SwarmRouter


class TestReviewFromFeatures:
    """Test SwarmRouter.review_from_features() — Go bridge path."""

    def setup_method(self) -> None:
        """Create router with default thresholds."""
        self.router = SwarmRouter(
            domains=[],
            clean_threshold=0.3,
            llm_threshold=0.7,
        )

    def test_clean_code_features(self) -> None:
        """All features zero → CLEAN."""
        features = {
            "has_n_plus_one": 0.0,
            "has_select_star": 0.0,
            "has_empty_catch": 0.0,
            "complexity": 0.0,
        }
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.CLEAN
        assert result.response is None
        assert result.confidence > 0.5

    def test_n_plus_one_detected(self) -> None:
        """N+1 query → TEMPLATE with Russian response."""
        features = {
            "has_n_plus_one": 1.0,
            "has_select_star": 0.0,
            "has_empty_catch": 0.0,
        }
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.TEMPLATE
        assert result.response is not None
        assert "N+1" in result.response

    def test_empty_catch_detected(self) -> None:
        """Empty catch → TEMPLATE with Исключение warning."""
        features = {
            "has_empty_catch": 1.0,
            "has_n_plus_one": 0.0,
            "complexity": 1.0,
        }
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.TEMPLATE
        assert result.response is not None
        assert "Исключение" in result.response

    def test_high_complexity_llm_required(self) -> None:
        """Very high scores → LLM_REQUIRED."""
        features = {
            "has_n_plus_one": 1.0,
            "has_select_star": 1.0,
            "has_empty_catch": 1.0,
            "has_deep_nesting": 1.0,
            "complexity": 15.0,
        }
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.LLM_REQUIRED
        assert result.confidence > 0.5

    def test_empty_features(self) -> None:
        """Empty dict → CLEAN."""
        result = self.router.review_from_features({})
        assert result.decision == RouterDecision.CLEAN

    def test_scores_contain_all_domains(self) -> None:
        """Result scores should have all 4 domain keys."""
        features = {"has_n_plus_one": 0.5}
        result = self.router.review_from_features(features)
        assert "query_optimizer" in result.scores
        assert "error_predictor" in result.scores
        assert "bsl_pattern" in result.scores
        assert "bsl_quality" in result.scores

    def test_select_star_template(self) -> None:
        """SELECT * → template about unnecessary fields."""
        features = {"has_select_star": 1.0}
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.TEMPLATE
        assert "ВЫБРАТЬ" in result.response or "поля" in result.response

    def test_deep_nesting_template(self) -> None:
        """Deep nesting → template about decomposition."""
        features = {"has_deep_nesting": 1.0}
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.TEMPLATE
        assert "вложенност" in result.response.lower()

    def test_multiple_issues_combined(self) -> None:
        """Multiple issues → longest/first matching template."""
        features = {
            "has_n_plus_one": 1.0,
            "has_empty_catch": 1.0,
        }
        result = self.router.review_from_features(features)
        # Should catch at least one issue
        assert result.decision in (RouterDecision.TEMPLATE, RouterDecision.LLM_REQUIRED)
        assert result.response is not None

    def test_unknown_features_ignored(self) -> None:
        """Unknown Go features should not crash."""
        features = {
            "unknown_go_feature": 1.0,
            "another_future_field": 0.5,
        }
        result = self.router.review_from_features(features)
        assert result.decision == RouterDecision.CLEAN
