# Ollama Client Guide

## Обзор

`OllamaClient` - универсальный клиент для работы с локальными моделями через Ollama. Поддерживает различные модели: llama3, mistral, codellama, qwen2.5-coder и другие.

## Установка Ollama

```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Скачайте установщик с https://ollama.ai/download

# Проверка установки
ollama --version
```

## Загрузка моделей

```bash
# Llama3
ollama pull llama3

# Mistral
ollama pull mistral

# CodeLlama
ollama pull codellama

# Qwen2.5 Coder
ollama pull qwen2.5-coder
```

## Использование

### Базовое использование

```python
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig

async def example():
    config = OllamaConfig(
        base_url="http://localhost:11434",
        model_name="llama3",
    )
    
    client = OllamaClient(config=config)
    
    result = await client.generate("Привет, как дела?")
    print(result["text"])
    
    await client.close()
```

### Context Manager

```python
async with OllamaClient(OllamaConfig(model_name="mistral")) as client:
    result = await client.generate("Объясни, как работает Python")
    print(result["text"])
```

### Список доступных моделей

```python
client = OllamaClient(OllamaConfig())
models = await client.list_models()
print(f"Доступные модели: {models}")
```

### Проверка доступности модели

```python
is_available = await client.check_model_available("llama3")
if is_available:
    result = await client.generate("Test", model_name="llama3")
```

### Генерация с параметрами

```python
result = await client.generate(
    prompt="Создай функцию на Python",
    model_name="codellama",
    temperature=0.7,
    max_tokens=2048,
    system_prompt="Ты опытный Python разработчик",
)
```

### JSON формат ответа

```python
result = await client.generate(
    prompt="Верни JSON с информацией о пользователе",
    response_format="json",
)
# result["text"] содержит JSON строку
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
config = OllamaConfig(
    base_url="http://localhost:11434",
    model_name="qwen2.5-coder",
    timeout=120,
    verify_ssl=False,  # Для самоподписанных сертификатов
    max_retries=3,
)
```

## Поддерживаемые модели

### Llama3
- Название: `llama3`
- Использование: общие задачи, тексты на английском
- Максимальные токены: 8192

### Mistral
- Название: `mistral`
- Использование: рассуждения, общие задачи
- Максимальные токены: 8192

### CodeLlama
- Название: `codellama`
- Использование: генерация и ревью кода
- Максимальные токены: 16384

### Qwen2.5 Coder
- Название: `qwen2.5-coder`
- Использование: продвинутая генерация кода
- Максимальные токены: 32768

## Интеграция с LLM Provider Abstraction

Ollama модели автоматически регистрируются в `LLMProviderAbstraction`:

```python
from src.ai.llm_provider_abstraction import LLMProviderAbstraction, QueryType

abstraction = LLMProviderAbstraction()

# Автоматический выбор Ollama модели для генерации кода
provider = abstraction.select_provider(
    QueryType.CODE_GENERATION,
    max_cost=0.0,  # Бесплатно
)

if provider and provider.provider_id == "ollama":
    print(f"Выбрана модель: {provider.model_name}")
```

## Использование через Orchestrator

Ollama модели можно использовать через `AIOrchestrator`:

```python
from src.ai.orchestrator import AIOrchestrator

orchestrator = AIOrchestrator()

result = await orchestrator.process_query(
    "Создай функцию на Python",
    context={
        "query_type": "code_generation",
        "preferred_provider": "ollama",
    },
)
```

## Обработка ошибок

```python
from src.ai.clients.exceptions import LLMNotConfiguredError, LLMCallError

try:
    result = await client.generate("Test")
except LLMNotConfiguredError:
    print("Ollama не настроен. Установите Ollama и настройте OLLAMA_HOST")
except LLMCallError as e:
    print(f"Ошибка при вызове Ollama: {e}")
```

## Performance

### Локальное выполнение

- Латентность: 2-4 секунды (зависит от модели и железа)
- Пропускная способность: зависит от GPU/CPU
- Стоимость: 0.0 (бесплатно)

### Оптимизация

1. Используйте модели меньшего размера для быстрого ответа
2. Настройте `max_tokens` для ограничения длины ответа
3. Используйте GPU для ускорения (если доступно)

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
```

### Таймаут

Увеличьте `timeout` в конфигурации:

```python
config = OllamaConfig(timeout=120)  # 2 минуты
```

## Best Practices

1. Используйте подходящую модель для задачи (codellama для кода, mistral для рассуждений)
2. Настройте `max_tokens` для ограничения длины ответа
3. Используйте `system_prompt` для контекста задачи
4. Кэшируйте результаты для повторяющихся запросов
5. Используйте context manager для автоматического закрытия соединений

## Примеры использования

### Генерация кода

```python
client = OllamaClient(OllamaConfig(model_name="codellama"))

result = await client.generate(
    prompt="Создай функцию на Python для вычисления факториала",
    system_prompt="Ты опытный Python разработчик. Пиши чистый код с документацией.",
    max_tokens=2048,
)

print(result["text"])
```

### Анализ текста

```python
client = OllamaClient(OllamaConfig(model_name="mistral"))

result = await client.generate(
    prompt="Проанализируй следующий текст и выдели основные идеи: ...",
    system_prompt="Ты аналитик, специализирующийся на анализе текстов.",
)
```

### Структурированный вывод

```python
result = await client.generate(
    prompt="Верни информацию о пользователе в формате JSON",
    response_format="json",
    system_prompt="Ты помощник, который возвращает данные в формате JSON.",
)

import json
data = json.loads(result["text"])
print(data)
```

