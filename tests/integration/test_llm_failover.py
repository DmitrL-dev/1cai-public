
import pytest


@pytest.mark.skip(
    reason="Будет активирован после реализации LLM Gateway и fallback-механизмов"
)
def test_llm_failover_smoke():
    """Плейсхолдер smoke-теста: проверяет, что можно переключиться на fallback."""
    assert True
