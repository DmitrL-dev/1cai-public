
"""
Real-World Examples - Примеры использования революционных компонентов
====================================================================

Практические примеры использования всех революционных компонентов
в реальных сценариях разработки на 1C
"""

import asyncio
import logging

from src.ai.code_dna import CodeDNAEngine
from src.ai.advanced_orchestrator import AdvancedAIOrchestrator
from src.ai.predictive_code_generation import (PredictiveCodeGenerator,
                                               Requirement)
from src.ai.self_healing_code import SelfHealingCode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_automatic_bug_fixing():
    """
    Пример 1: Автоматическое исправление багов
    
    Сценарий: AI агент сгенерировал код с ошибкой,
    Self-Healing Code автоматически исправляет её
    """
    logger.info("=== Example 1: Automatic Bug Fixing ===")
    
    from src.ai.llm_provider_abstraction import LLMProviderAbstraction
    from src.infrastructure.event_bus import EventBus
    
    llm_provider = LLMProviderAbstraction()
    event_bus = EventBus()
    await event_bus.start()
    
    healing = SelfHealingCode(llm_provider, event_bus)
    
    # Симуляция ошибки в AI-сгенерированном коде
    try:
        # Код с ошибкой (например, деление на ноль)
        result = 10 / 0
    except ZeroDivisionError as e:
        # Self-Healing автоматически исправляет
        fix = await healing.handle_error(
            e,
            context={
                "file_path": "src/generated/calculation.bsl",
                "line_number": 42,
                "code_snippet": "Результат = 10 / 0;"
            }
        )
        
        if fix:
            logger.info(f"Bug fixed automatically: {fix.id}")
            logger.info(f"Fix description: {fix.description}")
            logger.info(f"Fixed code: {fix.fixed_code}")
    
    await event_bus.stop()


async def example_2_self_improving_ai():
    """
    Пример 2: Самоулучшающийся AI
    
    Сценарий: AI система автоматически улучшает себя
    на основе метрик производительности
    """
    logger.info("=== Example 2: Self-Improving AI ===")
    
    orchestrator = AdvancedAIOrchestrator()
    await orchestrator.start()
    
    # Обработка нескольких запросов для сбора метрик
    for i in range(5):
        await orchestrator.process_query(f"Query {i}")
        await asyncio.sleep(0.5)
    
    # Запуск эволюции
    evolution_result = await orchestrator.evolve()
    
    logger.info(f"Evolution status: {evolution_result.get('status')}")
    logger.info(f"Improvements applied: {evolution_result.get('improvements_applied', 0)}")
    
    await orchestrator.stop()


async def example_3_distributed_agent_collaboration():
    """
    Пример 3: Коллаборация распределенных агентов
    
    Сценарий: Несколько агентов работают вместе
    для решения сложной задачи
    """
    logger.info("=== Example 3: Distributed Agent Collaboration ===")
    
    orchestrator = RevolutionaryAIOrchestrator()
    await orchestrator.start()
    
    # Создание задачи для команды агентов
    task_description = """
    Разработать новую функциональность:
    1. Developer: Создать код
    2. QA Engineer: Написать тесты
    3. Architect: Проверить архитектуру
    """
    
    result = await orchestrator.coordinate_agents(
        task_description,
        ["developer", "qa_engineer", "architect"]
    )
    
    logger.info(f"Task ID: {result['task_id']}")
    logger.info(f"Status: {result['status']}")
    logger.info(f"Network stats: {result['network_stats']}")
    
    await orchestrator.stop()


async def example_4_evolutionary_code_improvement():
    """
    Пример 4: Эволюционное улучшение кода
    
    Сценарий: Code DNA система эволюционирует код
    для улучшения производительности
    """
    logger.info("=== Example 4: Evolutionary Code Improvement ===")
    
    engine = CodeDNAEngine()
    
    # Исходный код
    original_code = """
    Функция ВычислитьСумму(Массив)
        Сумма = 0;
        Для Каждого Элемент Из Массив Цикл
            Сумма = Сумма + Элемент;
        КонецЦикла;
        Возврат Сумма;
    КонецФункции
    """
    
    # Преобразование в ДНК
    dna = engine.code_to_dna(original_code)
    logger.info(f"Code converted to DNA: {len(dna.genes)} genes")
    
    # Функция оценки (fitness function)
    async def calculate_fitness(code: str) -> float:
        # Упрощенная версия: больше строк = лучше (в реальности сложнее)
        return len(code) / 100.0
    
    # Эволюция
    best_dna = await engine.evolve(
        original_code,
        fitness_fn=calculate_fitness,
        generations=5
    )
    
    # Получение улучшенного кода
    improved_code = engine.dna_to_code(best_dna)
    logger.info(f"Improved code fitness: {best_dna.fitness}")
    logger.info(f"Improved code:\n{improved_code}")


async def example_5_predictive_development():
    """
    Пример 5: Проактивная разработка
    
    Сценарий: Predictive Generation предсказывает
    будущие требования и готовит код заранее
    """
    logger.info("=== Example 5: Predictive Development ===")
    
    from src.ai.llm_provider_abstraction import LLMProviderAbstraction
    from src.infrastructure.event_bus import EventBus
    
    llm_provider = LLMProviderAbstraction()
    event_bus = EventBus()
    await event_bus.start()
    
    generator = PredictiveCodeGenerator(llm_provider, event_bus)
    
    # Добавление требований
    requirements = [
        Requirement("Добавить отчет по продажам", "reporting"),
        Requirement("Интеграция с внешним API", "integration"),
        Requirement("Улучшить производительность", "performance")
    ]
    
    for req in requirements:
        generator.add_requirement(req)
    
    # Предсказание и подготовка
    result = await generator.predict_and_prepare(horizon_days=30)
    
    logger.info(f"Predictions generated: {result['predictions_count']}")
    logger.info(f"Code generated ahead: {result['generated_count']}")
    logger.info(f"Code prepared: {result['prepared_count']}")
    
    await event_bus.stop()


async def example_6_event_driven_ml_training():
    """
    Пример 6: Event-Driven ML Training
    
    Сценарий: ML обучение через Event-Driven Architecture
    вместо Celery
    """
    logger.info("=== Example 6: Event-Driven ML Training ===")
    
    from src.infrastructure.event_bus import (EventBus, EventPublisher,
                                              EventType)
    
    event_bus = EventBus()
    await event_bus.start()
    
    publisher = EventPublisher(event_bus, "ml-trainer")
    
    # Публикация события начала обучения
    event = await publisher.publish(
        EventType.ML_TRAINING_STARTED,
        payload={
            "model": "classification",
            "dataset": "train.csv",
            "epochs": 10
        }
    )
    
    logger.info(f"Training event published: {event.id}")
    
    # Обработка события (в реальности через handler)
    await asyncio.sleep(0.5)
    
    # Публикация события завершения
    await publisher.publish(
        EventType.ML_TRAINING_COMPLETED,
        payload={
            "model": "classification",
            "accuracy": 0.95
        }
    )
    
    await event_bus.stop()


async def main():
    """Запуск всех примеров"""
    examples = [
        example_1_automatic_bug_fixing,
        example_2_self_improving_ai,
        example_3_distributed_agent_collaboration,
        example_4_evolutionary_code_improvement,
        example_5_predictive_development,
        example_6_event_driven_ml_training
    ]
    
    for example in examples:
        try:
            await example()
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Example failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())

