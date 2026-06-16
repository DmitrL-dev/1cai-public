# Интеграция Kimi-K2-Thinking

## Обзор

Kimi-K2-Thinking - это state-of-the-art thinking модель от Moonshot AI с:
- **1T параметров** (MoE архитектура), активируется 32B
- **256k context window** - поддержка очень длинных контекстов
- **Native INT4 quantization** - 2x ускорение без потери качества
- **Deep thinking & tool orchestration** - многошаговое рассуждение
- **Stable long-horizon agency** - стабильная работа на 200-300 последовательных вызовах инструментов

## Установка и настройка

Kimi-K2-Thinking поддерживает два режима работы:
- **API режим** - использование облачного API Moonshot AI
- **Локальный режим** - запуск через Ollama (рекомендуется для приватности и контроля)

### 1. Локальный режим (рекомендуется)

#### 1.1. Установка Ollama

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Скачайте установщик с https://ollama.com/download
```

#### 1.2. Загрузка модели Kimi-K2-Thinking

```bash
ollama pull kimi-k2-thinking:cloud
```

#### 1.3. Настройка в `.env`

```bash
KIMI_MODE=local
KIMI_LOCAL_MODEL=kimi-k2-thinking:cloud
KIMI_OLLAMA_URL=http://localhost:11434  # или использует OLLAMA_HOST
KIMI_TEMPERATURE=1.0
KIMI_MAX_TOKENS=4096
KIMI_TIMEOUT=300.0
```

### 2. API режим (облачный)

#### 2.1. Получение API ключа

1. Зарегистрируйтесь на [platform.moonshot.ai](https://platform.moonshot.ai)
2. Получите API ключ в личном кабинете
3. Добавьте в `.env`:

```bash
KIMI_MODE=api
KIMI_API_KEY=your_api_key_here
KIMI_API_URL=https://api.moonshot.cn/v1  # Опционально
KIMI_MODEL=moonshotai/Kimi-K2-Thinking   # Опционально
KIMI_TEMPERATURE=1.0                      # Рекомендуется 1.0
KIMI_MAX_TOKENS=4096                      # Опционально
KIMI_TIMEOUT=300.0                        # 5 минут для thinking
```

### 3. Использование клиента

```python
from src.ai.clients.kimi_client import KimiClient

# Создание клиента (автоматически определяет режим из KIMI_MODE)
client = KimiClient()

# Проверка конфигурации
if client.is_configured:
    # Проверка режима
    if client.is_local:
        # Проверка загрузки модели в Ollama
        if await client.check_model_loaded():
            print("✅ Kimi модель загружена в Ollama")
        else:
            print("⚠️ Модель не загружена. Запустите: ollama pull kimi-k2-thinking:cloud")
    
    # Простой запрос (работает в обоих режимах)
    result = await client.generate(
        prompt="Напиши функцию для расчета НДС в 1С",
        system_prompt="Ты эксперт по 1С разработке",
        temperature=1.0
    )
    
    print(result["text"])  # Сгенерированный код
    print(result["reasoning_content"])  # Шаги рассуждения (только в API режиме)
```

### 4. Преимущества локального режима

- ✅ **Приватность** - данные не отправляются в облако
- ✅ **Контроль** - полный контроль над моделью
- ✅ **Без лимитов** - нет ограничений API
- ✅ **Бесплатно** - только стоимость GPU/электричества
- ⚠️ **Требует GPU** - рекомендуется NVIDIA GPU с 16GB+ VRAM

## Интеграция в AI Orchestrator

Kimi-K2-Thinking автоматически используется в AI Orchestrator для:
- **Code Generation** - приоритет 1 (лучше для сложных задач)
- **Architecture** - приоритет 1 (отличное многошаговое рассуждение)
- **Optimization** - приоритет 1 (глубокий анализ кода)

### Автоматический fallback

Если Kimi не настроен, система автоматически использует:
- Qwen3-Coder для генерации кода
- OpenAI для архитектурных задач
- Другие доступные сервисы

## Tool Calling

Kimi-K2-Thinking поддерживает tool calling для автономной работы:

```python
from src.ai.clients.kimi_client import KimiClient

client = KimiClient()

# Определение инструментов
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Получить погоду в городе",
        "parameters": {
            "type": "object",
            "required": ["city"],
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Название города"
                }
            }
        }
    }
}]

# Маппинг инструментов на функции
tool_map = {
    "get_weather": lambda city: {"weather": "Sunny", "city": city}
}

# Многошаговый диалог с инструментами
messages = [
    {"role": "system", "content": "You are Kimi, an AI assistant."},
    {"role": "user", "content": "Какая погода в Москве? Используй инструмент."}
]

result = await client.chat_with_tools(
    messages=messages,
    tools=tools,
    tool_map=tool_map,
    max_iterations=10
)

print(result["text"])  # Финальный ответ
print(result["reasoning_content"])  # Шаги рассуждения
print(result["tool_calls"])  # Вызванные инструменты
```

## Особенности

### Reasoning Content

Kimi-K2-Thinking возвращает `reasoning_content` - шаги рассуждения модели:

```python
result = await client.generate(
    prompt="Сравни 9.11 и 9.9, подумай внимательно",
    temperature=1.0
)

print(result["text"])  # Финальный ответ
print(result["reasoning_content"])  # Процесс рассуждения
```

### Рекомендуемые настройки

- **Temperature: 1.0** - рекомендуется для thinking моделей
- **Max tokens: 4096** - достаточно для большинства задач
- **Timeout: 300s** - 5 минут для сложных рассуждений

### Best Practices

1. **Используйте для сложных задач** - Kimi лучше всего подходит для:
   - Многошагового анализа кода
   - Архитектурного проектирования
   - Сложной оптимизации
   - Задач требующих глубокого рассуждения

2. **Tool calling для автономной работы** - Kimi может выполнять до 200-300 последовательных вызовов инструментов без деградации

3. **Обрабатывайте reasoning_content** - используйте шаги рассуждения для:
   - Отладки
   - Объяснения решений пользователю
   - Улучшения промптов

## Примеры использования

### Генерация кода с объяснением

```python
result = await client.generate(
    prompt="Напиши функцию для расчета НДС с учетом всех особенностей 1С",
    system_prompt="Ты эксперт по 1С разработке",
    temperature=1.0
)

code = result["text"]
reasoning = result["reasoning_content"]

# Сохранить код и объяснение
save_code_with_explanation(code, reasoning)
```

### Оптимизация кода

```python
code_to_optimize = """
Функция РасчетНДС(Сумма, СтавкаНДС)
    Для Каждого Элемент Из Массив Цикл
        Запрос = Новый Запрос;
        Запрос.Текст = "SELECT * FROM Документы WHERE Ид = " + Элемент.Ид;
        Результат = Запрос.Выполнить();
    КонецЦикла;
КонецФункции
"""

result = await client.generate(
    prompt=f"Оптимизируй этот код:\n\n{code_to_optimize}",
    system_prompt="Ты эксперт по оптимизации 1С кода",
    temperature=1.0
)

optimized_code = result["text"]
improvements = result["reasoning_content"]  # Объяснение улучшений
```

## Производительность

- **Latency**: ~2-5 секунд для простых запросов, до 30 секунд для сложных рассуждений
- **Throughput**: Зависит от API лимитов Moonshot AI
- **Cost**: См. тарифы на [platform.moonshot.ai](https://platform.moonshot.ai)

## Troubleshooting

### Ошибка "Kimi API key is not configured"

Убедитесь, что `KIMI_API_KEY` установлен в `.env` файле.

### Timeout ошибки

Увеличьте `KIMI_TIMEOUT` для сложных задач:
```bash
KIMI_TIMEOUT=600.0  # 10 минут
```

### Ошибки формата сообщений

Kimi использует стандартный OpenAI формат. Убедитесь, что `content` - это строка, а не массив.

## Дополнительные ресурсы

- [Hugging Face Model Card](https://huggingface.co/moonshotai/Kimi-K2-Thinking)
- [Moonshot AI Platform](https://platform.moonshot.ai)
- [API Documentation](https://platform.moonshot.ai/docs)

