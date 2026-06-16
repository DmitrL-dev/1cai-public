# Руководство по интеграции Когнитивной Памяти (GAM)

Этот документ содержит подробные инструкции по работе с системой Когнитивной Памяти (General Agentic Memory - GAM), внедренной в стек 1C AI.

## Обзор

GAM добавляет системе "человекоподобную" память, позволяя ей:
1.  **Запоминать** взаимодействия и факты с учетом их происхождения (Provenance).
2.  **Забывать** устаревшую информацию со временем (Ebbinghaus Decay).
3.  **Вспоминать** релевантный контекст перед ответом (JIT Context Compilation).

## 1. Конфигурация

Система работает "из коробки" с настройками по умолчанию, но может быть сконфигурирована через переменные окружения (в будущем) или напрямую в коде.

### Основные компоненты

Все компоненты находятся в `src.ai.memory`:
-   `Memorizer`: Менеджер памяти.
-   `Consolidator`: Фоновый процесс обслуживания.
-   `ContextCompiler`: Компилятор контекста.

## 2. Использование API

### Запоминание (Remembering)

Чтобы сохранить факт или взаимодействие, используйте метод `remember` у экземпляра `Memorizer` (доступен через `orchestrator.memorizer`).

```python
from src.ai.memory.schemas import MemorySource
from src.ai.orchestrator import get_orchestrator

orchestrator = get_orchestrator()
if orchestrator.memorizer:
    orchestrator.memorizer.remember(
        content="Пользователь предпочитает ответы на русском языке.",
        source=MemorySource.USER,  # Источник: USER, INFERENCE, DOCUMENTATION и т.д.
        confidence=1.0,            # Уверенность (0.0 - 1.0)
        metadata={"category": "preference"}
    )
```

### Вспоминание (Recalling)

Для поиска воспоминаний используйте `recall`. Метод автоматически фильтрует забытые факты.

```python
memories = orchestrator.memorizer.recall(
    query="языковые предпочтения", # В текущей версии поиск по тексту (фильтр), в будущем - векторный
    min_retention=0.2              # Минимальный порог удержания (0.0 - 1.0)
)

for m in memories:
    print(f"[{m.provenance.source}] {m.content} (Сила: {m.strength:.2f})")
```

### Подкрепление (Reinforcement)

Если воспоминание оказалось полезным, его нужно "подкрепить", чтобы сбросить кривую забывания.

```python
# Если мы использовали воспоминание m
orchestrator.memorizer.reinforce(m.id)
```

## 3. Интеграция с Оркестратором

GAM уже интегрирован в `AIOrchestrator`.

-   **Автоматическое запоминание**: Все успешные ответы на запросы сохраняются с источником `INFERENCE`.
-   **JIT Брифинг**: Перед выполнением запроса `ContextCompiler` ищет релевантные факты и добавляет их в контекст под ключом `memory_briefing`.

Чтобы отключить память для конкретного запроса, передайте `use_memory=False` в контексте:

```python
response = await orchestrator.process_query(
    "Секретный запрос", 
    context={"use_memory": False}
)
```

## 4. Расширение и Обслуживание

### Добавление новых источников памяти

В `src/ai/memory/schemas.py` добавьте новые значения в `MemorySource` Enum:

```python
class MemorySource(str, Enum):
    # ... существующие ...
    MY_NEW_SOURCE = "my_source"
```

### Настройка кривой забывания

Логика забывания находится в `src/ai/memory/schemas.py` в методе `calculate_retention`. Вы можете настроить параметры `stability` и влияние `access_count` на силу памяти.

### Фоновое обслуживание (Consolidation)

Класс `Consolidator` отвечает за очистку (Pruning) и сны (Dreaming). В настоящее время он должен вызываться периодически (например, через Cron или планировщик задач).

```python
from src.ai.memory.consolidator import Consolidator

consolidator = Consolidator(orchestrator.memorizer)
consolidator.run_maintenance() # Запустит очистку и генерацию снов
```

## 5. Отладка

Логи GAM пишутся в стандартный логгер приложения. Ищите записи с `src.ai.memory` или `src.ai.orchestrator` с упоминанием "GAM".

Пример лога:
`INFO src.ai.orchestrator: Context enriched with GAM briefing (briefing_len=150)`
