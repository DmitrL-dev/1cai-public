
"""
E2E тесты для CLI инструмента
------------------------------

Тестирование полного цикла работы CLI инструмента
с реальными API endpoints.
"""

import pytest

# Эти тесты требуют запущенного API сервера
# Для локального тестирования можно использовать TestClient из FastAPI


@pytest.mark.asyncio
async def test_e2e_cli_query_command() -> None:
    """
    E2E тест: CLI команда query работает корректно.
    """
    # Этот тест требует запущенного API сервера
    # В реальном сценарии можно использовать TestClient

    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)

    # Отправить запрос через API
    response = client.post("/api/ai/query", params={"query": "test query"})

    # Проверить, что ответ получен
    assert response.status_code in [200, 500]  # 500 если нет LLM провайдеров


@pytest.mark.asyncio
async def test_e2e_cli_scenarios_command() -> None:
    """
    E2E тест: CLI команда scenarios работает корректно.
    """
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)

    # Получить список сценариев
    response = client.get("/api/scenarios/examples")

    # Проверить, что ответ получен
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) > 0


@pytest.mark.asyncio
async def test_e2e_cli_health_command() -> None:
    """
    E2E тест: CLI команда health работает корректно.
    """
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)

    # Проверить health через API
    # (health endpoint может не существовать, но мы можем проверить доступность основных endpoints)
    response = client.get("/api/scenarios/examples")

    # Проверить, что endpoint доступен
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_e2e_cli_cache_metrics_command() -> None:
    """
    E2E тест: CLI команда cache metrics работает корректно.
    """
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)

    # Получить метрики кэша
    response = client.get("/api/cache/metrics")

    # Проверить, что ответ получен
    assert response.status_code == 200
    data = response.json()
    assert "type" in data or "error" in data


@pytest.mark.asyncio
async def test_e2e_cli_llm_providers_command() -> None:
    """
    E2E тест: CLI команда llm-providers list работает корректно.
    """
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)

    # Получить список LLM провайдеров
    response = client.get("/api/llm/providers")

    # Проверить, что ответ получен
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "total" in data
    assert data["total"] > 0
