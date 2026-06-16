
from src.services.llm_gateway import load_llm_gateway


def test_llm_gateway_simulation_architect():
    gateway = load_llm_gateway()
    response = gateway.generate("Нужна диаграмма mermaid для сервиса", role="architect")

    assert response.metadata.get("simulation") is True
    assert response.metadata.get("scenario") == "architect-diagram"
    assert "mermaid" in response.response.lower()


def test_llm_gateway_simulation_devops():
    gateway = load_llm_gateway()
    response = gateway.generate("latency ошибка при деплое", role="devops")

    assert response.metadata.get("simulation") is True
    assert response.metadata.get("scenario") == "devops-fallback"
    assert "health-check" in response.response.lower()
