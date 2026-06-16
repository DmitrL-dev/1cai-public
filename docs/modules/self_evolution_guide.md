# Руководство по Самоэволюции (Self-Evolution)

Этот документ описывает архитектуру и использование компонентов Самоэволюции (Phases 1-3) в стеке 1C AI.

## Обзор

Система Самоэволюции позволяет ИИ агенту:
1.  **Чувствовать (Senses)**: Собирать метрики производительности и ошибки.
2.  **Думать (Brain)**: Анализировать стратегии и выбирать лучшие (Meta-Optimization).
3.  **Действовать (Hands)**: Вносить изменения в код через безопасные Pull Requests (RSI).

## 1. Инструментарий (Senses)

### TelemetryCollector

Сборщик метрик Prometheus. Автоматически собирает данные о длительности выполнения, ошибках и успешности стратегий.

**Расположение:** `src/infrastructure/telemetry/collector.py`

**Использование:**
Интегрирован в `AIOrchestrator`. Метрики доступны по адресу `/metrics` (если включен Prometheus exporter).

**Ключевые метрики:**
-   `ai_strategy_duration_seconds`: Время выполнения стратегии.
-   `ai_strategy_errors_total`: Количество ошибок.
-   `ai_evolution_cycle_total`: Количество циклов самоэволюции.

## 2. Мозг (The Brain)

### StrategySelector (Multi-Armed Bandit)

Выбирает лучшую стратегию (LLM провайдера) для задачи на основе исторических данных. Использует алгоритм Epsilon-Greedy.

**Расположение:** `src/ai/optimization/strategy_selector.py`

**Конфигурация:**
-   `epsilon`: Вероятность выбора случайной стратегии (исследование). По умолчанию 0.1.
-   `decay`: Коэффициент забывания старых наград.

**Использование:**

```python
from src.ai.optimization.strategy_selector import get_strategy_selector

selector = get_strategy_selector()
best_strategy = selector.select_strategy(
    candidates=["qwen", "kimi", "gigachat"],
    context="code_generation"
)
```

### Strike3Reflector (Self-Critique)

Анализирует ошибки и предлагает улучшения. Если стратегия ошибается 3 раза подряд ("Strike 3"), запускается глубокий анализ.

**Расположение:** `src/ai/optimization/strike3_reflector.py`

**Логика:**
1.  Мониторит историю выполнения.
2.  При обнаружении паттерна ошибок генерирует `OptimizationProposal`.
3.  Предложение отправляется в `SelfEvolvingAI` для применения.

## 3. Руки (The Hands / RSI)

### GitAutomation

Безопасный интерфейс для работы с Git. Позволяет агенту создавать ветки, коммитить изменения и открывать PR.

**Расположение:** `src/infrastructure/git_automation.py`

**Безопасность (Rule of Two):**
Агент **никогда** не пушит в `main` напрямую. Все изменения проходят через PR, требующий одобрения человека.

**Использование:**

```python
from src.infrastructure.git_automation import GitAutomation

git = GitAutomation()
pr_url = await git.create_pr(
    title="Fix: Optimize Qwen Strategy",
    body="Fixed timeout issue in Qwen client.",
    branch_name="fix/qwen-optimization",
    files={"src/ai/strategies/qwen.py": "new_content"}
)
```

### PromptOptimizer

Автоматически улучшает системные промпты на основе анализа неудачных ответов.

**Расположение:** `src/ai/optimization/prompt_optimizer.py`

**Процесс:**
1.  Получает плохой пример (запрос + плохой ответ).
2.  Генерирует улучшенную версию промпта.
3.  Создает PR с обновленным файлом промпта.

## 4. API Эволюции

Управление процессом эволюции доступно через REST API.

Подробности см. в [API_DEVOPS_AI_EVOLUTION.md](../API_DEVOPS_AI_EVOLUTION.md).

## 5. Тестирование

Для проверки компонентов самоэволюции используйте:

```bash
pytest tests/unit/test_self_evolution.py
pytest tests/integration/test_autonomy_loop.py
```
