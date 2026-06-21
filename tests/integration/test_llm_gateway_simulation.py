
import pytest

from src.services.llm_gateway import load_llm_gateway


@pytest.mark.asyncio
async def test_llm_gateway_simulation_architect():
    gateway = load_llm_gateway()
    # LLMGateway.generate is a coroutine; it must be awaited (the previous code
    # asserted on the un-awaited coroutine object → AttributeError on .metadata).
    response = await gateway.generate(
        "Нужна диаграмма mermaid для сервиса", role="architect"
    )

    assert response.metadata.get("simulation") is True
    assert response.metadata.get("scenario") == "architect-diagram"
    assert "mermaid" in response.response.lower()


@pytest.mark.asyncio
async def test_llm_gateway_simulation_devops():
    gateway = load_llm_gateway()
    response = await gateway.generate("latency ошибка при деплое", role="devops")

    assert response.metadata.get("simulation") is True
    assert response.metadata.get("scenario") == "devops-fallback"
    assert "health-check" in response.response.lower()
