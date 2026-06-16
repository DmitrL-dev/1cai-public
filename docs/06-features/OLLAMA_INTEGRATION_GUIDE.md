# Ollama Integration Guide

## Обзор

Ollama интеграция позволяет использовать локальные модели через Ollama клиент. Модели автоматически регистрируются в LLM Provider Abstraction и интегрированы в AIOrchestrator для автоматического выбора.

## Поддерживаемые модели

### Llama3
- **Название**: `llama3`
- **Использование**: общие задачи, тексты на английском
- **Максимальные токены**: 8192
- **Latency**: ~3000ms

### Mistral
- **Название**: `mistral`
- **Использование**: рассуждения, общие задачи
- **Максимальные токены**: 8192
- **Latency**: ~2500ms

### CodeLlama
- **Название**: `codellama`
- **Использование**: генерация и ревью кода
- **Максимальные токены**: 16384
- **Latency**: ~4000ms

### Qwen2.5 Coder
- **Название**: `qwen2.5-coder`
- **Использование**: продвинутая генерация кода
- **Максимальные токены**: 32768
- **Latency**: ~3500ms

## Автоматический выбор в Orchestrator

Ollama модели автоматически выбираются в следующих случаях:

### 1. Ограничение по стоимости (бесплатно)

```python
result = await orchestrator.process_query(
    "Создай функцию на Python",
    context={"max_cost": 0.0},
)
# Автоматически выберет Ollama модель (llama3, mistral, codellama, qwen2.5-coder)
```

### 2. Ограничение по риску (low risk)

```python
result = await orchestrator.process_query(
    "Объясни алгоритм",
    context={"preferred_risk_level": "low"},
)
# Выберет локальную модель с низким риском
```

### 3. Явный запрос локальных моделей

```python
result = await orchestrator.process_query(
    "Тестовый запрос",
    context={"use_local_models": True},
)
# Принудительно использует Ollama
```

### 4. Fallback для генерации кода

Если другие провайдеры недоступны:

```python
result = await orchestrator.process_query(
    "Создай функцию",
    context={"query_type": "code_generation"},
)
# Использует Ollama если Kimi/Напарник не доступны
```

## Интеграция с LLM Provider Abstraction

Ollama модели автоматически регистрируются в LLM Provider Abstraction:

```python
from src.ai.llm_provider_abstraction import LLMProviderAbstraction, QueryType, RiskLevel

abstraction = LLMProviderAbstraction()

# Автоматический выбор Ollama модели для генерации кода с ограничением по стоимости
provider = abstraction.select_provider(
    QueryType.CODE_GENERATION,
    max_cost=0.0,
    preferred_risk_level=RiskLevel.LOW,
)

if provider and provider.provider_id == "ollama":
    print(f"Выбрана модель: {provider.model_name}")
```

## Использование через API

### REST API

```bash
# Запрос с ограничением по стоимости (бесплатно)
curl -X POST "http://localhost:8000/api/ai/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Создай функцию на Python",
    "context": {
      "max_cost": 0.0,
      "preferred_risk_level": "low"
    }
  }'

# Явный запрос локальных моделей
curl -X POST "http://localhost:8000/api/ai/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Тестовый запрос",
    "context": {
      "use_local_models": true,
      "ollama_model": "codellama"
    }
  }'
```

## Конфигурация

### Переменные окружения

```bash
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="llama3"
export OLLAMA_TIMEOUT="60"
export OLLAMA_VERIFY_SSL="true"
```

### Программная конфигурация

```python
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig

config = OllamaConfig(
    base_url="http://localhost:11434",
    model_name="codellama",
    timeout=120,
    verify_ssl=False,  # Для самоподписанных сертификатов
)

client = OllamaClient(config=config)
```

## Выбор модели

Оркестратор автоматически выбирает подходящую модель на основе:
1. Типа запроса (code_generation, general, reasoning)
2. Ограничений по стоимости (max_cost)
3. Ограничений по риску (preferred_risk_level)
4. Compliance требований (152-ФЗ, GDPR)

### Примеры выбора

```python
# Генерация кода → codellama или qwen2.5-coder
# Общие задачи → llama3 или mistral
# Рассуждения → mistral
# Бесплатно → любая Ollama модель
# Низкий риск → Ollama модели (локальное исполнение)
```

## Performance

### Преимущества локальных моделей

- **Бесплатно**: cost_per_1k_tokens = 0.0
- **Низкий риск**: RiskLevel.LOW (локальное исполнение)
- **Compliance**: 152-ФЗ, GDPR (данные не покидают локальную среду)
- **Низкая latency**: 2-4 секунды (зависит от модели и железа)

### Рекомендации

1. Используйте GPU для ускорения (если доступно)
2. Выбирайте модель подходящего размера для задачи
3. Настройте `max_tokens` для ограничения длины ответа
4. Кэшируйте результаты для повторяющихся запросов

## Troubleshooting

### Ollama не запущен

```bash
# Запустить Ollama
ollama serve

# Проверить статус
curl http://localhost:11434/api/tags
```

### Модель не найдена

```bash
# Проверить загруженные модели
ollama list

# Загрузить модель
ollama pull llama3
ollama pull codellama
```

### Orchestrator не использует Ollama

1. Проверьте, что Ollama запущен: `curl http://localhost:11434/api/tags`
2. Проверьте конфигурацию: `OLLAMA_HOST` должен быть установлен
3. Используйте `use_local_models=True` в контексте для принудительного использования

## Best Practices

1. **Выбор модели**: используйте подходящую модель для задачи (codellama для кода, mistral для рассуждений)
2. **Кэширование**: кэшируйте результаты для повторяющихся запросов
3. **Ограничения**: настройте `max_tokens` и `temperature` для контроля качества и длины ответа
4. **Fallback**: используйте Ollama как fallback для других провайдеров
5. **Производительность**: используйте GPU если доступно для ускорения

## Примеры использования

### Генерация кода через Orchestrator

```python
from src.ai.orchestrator import AIOrchestrator

orchestrator = AIOrchestrator()

result = await orchestrator.process_query(
    "Создай функцию на Python для вычисления факториала",
    context={
        "max_cost": 0.0,  # Бесплатно
        "query_type": "code_generation",
    },
)

print(result["text"])
```

### Использование через LLM Provider Abstraction

```python
from src.ai.llm_provider_abstraction import LLMProviderAbstraction, QueryType, RiskLevel

abstraction = LLMProviderAbstraction()

# Выбор Ollama модели для генерации кода
provider = abstraction.select_provider(
    QueryType.CODE_GENERATION,
    max_cost=0.0,
    preferred_risk_level=RiskLevel.LOW,
)

if provider:
    print(f"Provider: {provider.provider_id}, Model: {provider.model_name}")
```

### Прямое использование OllamaClient

```python
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig

client = OllamaClient(OllamaConfig(model_name="codellama"))

result = await client.generate(
    "Создай функцию на Python",
    system_prompt="Ты опытный Python разработчик.",
    max_tokens=2048,
)

print(result["text"])
```

