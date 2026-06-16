
"""
Пример использования LLM Provider Abstraction для автоматического выбора провайдера

Этот пример демонстрирует:
1. Автоматический выбор провайдера на основе запроса
2. Учет compliance требований
3. Управление стоимостью и латентностью
"""

import asyncio

from src.ai.llm_provider_abstraction import LLMProviderAbstraction


async def llm_provider_selection_example():
    """Пример автоматического выбора LLM провайдера"""
    
    # Создать абстракцию
    provider = LLMProviderAbstraction()
    
    # Пример 1: Генерация BSL кода (русский язык, требуется 152-ФЗ)
    print("Пример 1: Генерация BSL кода для российского проекта")
    query1 = "Сгенерируй BSL код для справочника товаров с полями: Наименование, Код, Артикул"
    
    selected1 = provider.select_provider(
        query=query1,
        query_type="code_generation",
        language="ru",
        preferred_risk_level="low",
        compliance_requirements=["152-fz"]
    )
    
    print(f"Выбранный провайдер: {selected1.provider_id}")
    print(f"Причина: {selected1.reason}")
    print()
    
    # Пример 2: Code Review (английский, GDPR)
    print("Пример 2: Code Review для международного проекта")
    query2 = "Review this Python code for security vulnerabilities"
    
    selected2 = provider.select_provider(
        query=query2,
        query_type="code_review",
        language="en",
        preferred_risk_level="low",
        compliance_requirements=["gdpr"]
    )
    
    print(f"Выбранный провайдер: {selected2.provider_id}")
    print(f"Причина: {selected2.reason}")
    print()
    
    # Пример 3: Низкая стоимость (локальный провайдер)
    print("Пример 3: Выбор провайдера с минимальной стоимостью")
    query3 = "Explain the concept of microservices"
    
    selected3 = provider.select_provider(
        query=query3,
        query_type="explanation",
        language="en",
        preferred_risk_level="low",
        cost_preference="low"
    )
    
    print(f"Выбранный провайдер: {selected3.provider_id}")
    print(f"Стоимость: {selected3.estimated_cost}")
    print()
    
    # Пример 4: Минимальная латентность
    print("Пример 4: Выбор провайдера с минимальной латентностью")
    query4 = "Quick analysis of code quality"
    
    selected4 = provider.select_provider(
        query=query4,
        query_type="code_analysis",
        language="en",
        latency_preference="low"
    )
    
    print(f"Выбранный провайдер: {selected4.provider_id}")
    print(f"Ожидаемая латентность: {selected4.estimated_latency_ms}ms")
    print()
    
    # Пример 5: Использование выбранного провайдера
    print("Пример 5: Генерация ответа через выбранный провайдер")
    response = await selected1.generate(query1)
    print(f"Ответ: {response[:100]}...")
    print()


if __name__ == "__main__":
    asyncio.run(llm_provider_selection_example())
    print("✅ Примеры выполнены успешно!")

