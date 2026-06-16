# 1C AI Stack CLI Guide

**Версия:** 1.0.0  
**Дата:** Январь 2025

## Обзор

Унифицированный CLI инструмент для работы с платформой 1C AI Stack. Предоставляет удобный интерфейс для разработчиков для работы с AI Orchestrator, Scenario Hub, Unified Change Graph, кэшем и метриками.

## Установка

CLI инструмент находится в `scripts/cli/1cai_cli.py` и не требует отдельной установки. Просто убедитесь, что установлены зависимости:

```bash
pip install httpx
```

## Быстрый старт

### Базовое использование

```bash
# Отправить запрос в AI Orchestrator
python scripts/cli/1cai_cli.py query "Как создать функцию в 1С?"

# Получить список доступных сценариев
python scripts/cli/1cai_cli.py scenarios

# Проверить статус системы
python scripts/cli/1cai_cli.py health
```

### Использование через Makefile

```bash
# Отправить запрос
make cli-query TEXT="Как создать функцию в 1С?"

# Получить список сценариев
make cli-scenarios

# Проверить статус
make cli-health

# Получить метрики кэша
make cli-cache-metrics

# Список LLM провайдеров
make cli-llm-providers
```

## Команды

### `query` - Отправить запрос в AI Orchestrator

Отправляет запрос в AI Orchestrator и возвращает ответ.

```bash
python scripts/cli/1cai_cli.py query "Как оптимизировать запрос к базе данных?"
```

**Примеры:**

```bash
# Простой запрос
python scripts/cli/1cai_cli.py query "Создай функцию для расчета НДС"

# С форматированием таблицей
python scripts/cli/1cai_cli.py query "Покажи все модули" --format table
```

### `scenarios` - Получить список доступных сценариев

Получает список доступных сценариев из Scenario Hub.

```bash
# Все сценарии
python scripts/cli/1cai_cli.py scenarios

# С уровнем автономности
python scripts/cli/1cai_cli.py scenarios --autonomy A1_safe_automation
```

### `recommend` - Получить рекомендации сценариев

Получает рекомендации сценариев на основе запроса пользователя.

```bash
python scripts/cli/1cai_cli.py recommend "Нужно реализовать новую фичу" --max 5
```

### `impact` - Проанализировать влияние изменений

Анализирует влияние изменений в узлах графа.

```bash
python scripts/cli/1cai_cli.py impact node1 node2 node3 --max-depth 3
```

**Опции:**
- `--max-depth` - Максимальная глубина поиска зависимостей (по умолчанию: 3)
- `--no-tests` - Не включать тесты в анализ

### `llm-providers` - Работа с LLM провайдерами

#### Список провайдеров

```bash
python scripts/cli/1cai_cli.py llm-providers list
```

#### Выбор провайдера

```bash
python scripts/cli/1cai_cli.py llm-providers select code_generation \
    --max-cost 0.01 \
    --max-latency 2000 \
    --compliance 152-ФЗ GDPR \
    --risk-level low
```

**Параметры:**
- `query_type` - Тип запроса (code_generation, reasoning, russian_text, etc.)
- `--max-cost` - Максимальная стоимость за 1K токенов
- `--max-latency` - Максимальная latency в миллисекундах
- `--compliance` - Требуемое соответствие (152-ФЗ, GDPR, etc.)
- `--risk-level` - Предпочтительный уровень риска (low, medium, high)

### `cache` - Работа с кэшем

#### Метрики кэша

```bash
python scripts/cli/1cai_cli.py cache metrics
```

Возвращает:
- Hit rate (процент попаданий)
- Размер кэша
- Статистику использования

#### Инвалидация кэша

```bash
# Инвалидировать по тегам
python scripts/cli/1cai_cli.py cache invalidate --tags orchestrator ai_query

# Инвалидировать по типу запроса
python scripts/cli/1cai_cli.py cache invalidate --query-type code_generation

# Очистить весь кэш
python scripts/cli/1cai_cli.py cache invalidate --clear-all
```

### `health` - Проверить статус системы

Проверяет доступность основных endpoints системы.

```bash
python scripts/cli/1cai_cli.py health
```

Возвращает статус:
- `healthy` - Все endpoints доступны
- `degraded` - Некоторые endpoints недоступны
- `unhealthy` - Система недоступна

## Опции

### `--base-url`

Указать базовый URL API сервера (по умолчанию: `http://localhost:8000`):

```bash
python scripts/cli/1cai_cli.py --base-url http://api.example.com:8000 health
```

### `--format`

Формат вывода (по умолчанию: `json`):

```bash
# JSON формат
python scripts/cli/1cai_cli.py scenarios --format json

# Табличный формат (для некоторых команд)
python scripts/cli/1cai_cli.py scenarios --format table
```

## Примеры использования

### Полный workflow разработки

```bash
# 1. Проверить статус системы
python scripts/cli/1cai_cli.py health

# 2. Получить рекомендации сценариев для новой фичи
python scripts/cli/1cai_cli.py recommend "Реализовать интеграцию с внешним API" --max 3

# 3. Выбрать подходящий LLM провайдер
python scripts/cli/1cai_cli.py llm-providers select code_generation --risk-level low

# 4. Отправить запрос на генерацию кода
python scripts/cli/1cai_cli.py query "Создай функцию для работы с REST API"

# 5. Проверить метрики кэша
python scripts/cli/1cai_cli.py cache metrics
```

### Мониторинг и отладка

```bash
# Проверить метрики кэша
python scripts/cli/1cai_cli.py cache metrics

# Очистить кэш при проблемах
python scripts/cli/1cai_cli.py cache invalidate --clear-all

# Проверить доступность всех endpoints
python scripts/cli/1cai_cli.py health
```

### Интеграция в скрипты

```bash
#!/bin/bash
# Пример скрипта для автоматической проверки

STATUS=$(python scripts/cli/1cai_cli.py health --format json | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    echo "System is not healthy: $STATUS"
    exit 1
fi

echo "System is healthy"
```

## См. также

- [`AI_ORCHESTRATOR_GUIDE.md`](../06-features/AI_ORCHESTRATOR_GUIDE.md) - Гайд по AI Orchestrator
- [`SCENARIO_HUB_GUIDE.md`](../06-features/SCENARIO_HUB_GUIDE.md) - Гайд по Scenario Hub
- [`CODE_GRAPH_REFERENCE.md`](../architecture/CODE_GRAPH_REFERENCE.md) - Справочник по Unified Change Graph

