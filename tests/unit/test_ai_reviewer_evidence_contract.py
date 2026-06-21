import pytest

from src.ai.agents.code_review.ai_reviewer import (
    CODE_REVIEW_CONTRACT,
    AICodeReviewer,
)


SIMPLE_BSL = """
Функция ПолучитьДанные(ID)
    Возврат ID;
КонецФункции
"""


@pytest.mark.asyncio
async def test_ai_reviewer_env_key_alone_does_not_claim_llm_review(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reviewer = AICodeReviewer()

    result = await reviewer.review_code(SIMPLE_BSL, "module.bsl")

    assert result["mode"] == CODE_REVIEW_CONTRACT
    assert result["coverage"] == "deterministic_bsl_scanners"
    assert result["ai_review"]["status"] == "not_configured"
    assert result["ai_review"]["measured"] is False
    assert result["ai_review"]["llm_credentials_present"] is True
    assert result["ai_review"]["llm_adapter_available"] is False
    assert "LLM review adapter" in result["ai_review"]["required_evidence"]


@pytest.mark.asyncio
async def test_ai_reviewer_uses_injected_llm_adapter():
    class LLMReviewAdapter:
        async def review_code(self, code, ast):
            return [
                {
                    "severity": "LOW",
                    "issue": "Adapter finding",
                    "source": "llm_adapter",
                }
            ]

    reviewer = AICodeReviewer(llm_client=LLMReviewAdapter())

    result = await reviewer.review_code(SIMPLE_BSL, "module.bsl")

    assert result["ai_review"]["status"] == "executed"
    assert result["ai_review"]["measured"] is True
    assert result["coverage"] == "deterministic_bsl_scanners+llm_deep_review"
    assert result["issues"]["ai_suggestions"][0]["issue"] == "Adapter finding"
