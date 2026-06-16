# Copilot — Руководство пользователя

**Версия:** 1.0  
**Статус:** ✅ Production Ready  
**API Endpoint:** `/api/v1/copilot`

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Установка и настройка](#установка-и-настройка)
3. [API Reference](#api-reference)
4. [Примеры использования](#примеры-использования)
5. [Интеграция](#интеграция)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Обзор

### Что это такое?

**Copilot** — это AI-ассистент для разработки на 1C:Предприятие, который помогает писать код быстрее и качественнее. Поддерживает code completion, code generation, code explanation, и code search.

### Для кого предназначен?

- 👨‍💻 **Разработчики 1C** — автодополнение и генерация BSL кода
- 🎓 **Начинающие разработчики** — обучение через примеры и объяснения
- 🏢 **Команды разработки** — стандартизация кода и best practices
- 🔍 **Code reviewers** — быстрый поиск и анализ кода

### Основные возможности

✅ **Code Completion** — умное автодополнение кода (BSL, JavaScript, Python)  
✅ **Code Generation** — генерация кода по описанию на русском языке  
✅ **Code Explanation** — объяснение сложного кода простым языком  
✅ **Code Search** — семантический поиск по кодовой базе  
✅ **Refactoring Suggestions** — рекомендации по рефакторингу  
✅ **Bug Detection** — поиск потенциальных багов

---

## Установка и настройка

### Требования

**Минимальные:**
- Python 3.11+
- OpenAI API key или локальная LLM (Ollama)
- 8 GB RAM

**Рекомендуемые:**
- Python 3.12.7
- OpenAI GPT-4 или Claude 3.5
- 16 GB RAM
- GPU для локальных моделей

### Установка

```bash
# Copilot уже включен в 1C AI Stack
# Настройте API ключи в .env

# OpenAI
OPENAI_API_KEY=sk-...

# Или используйте локальную модель (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=codellama:13b
```

### Конфигурация

```bash
# .env файл
COPILOT_ENABLED=true
COPILOT_MODEL=gpt-4-turbo-preview
COPILOT_MAX_TOKENS=2000
COPILOT_TEMPERATURE=0.2
COPILOT_CACHE_TTL=3600

# Для BSL-specific features
BSL_PARSER_ENABLED=true
BSL_SYNTAX_CHECK=true
```

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1/copilot
```

### Endpoints

#### 1. Code Completion

**Endpoint:** `POST /api/v1/copilot/complete`

**Описание:** Автодополнение кода на основе контекста.

**Request:**
```json
{
  "code": "Функция ПолучитьДанныеКлиента(КодКлиента)\n    // ",
  "language": "bsl",
  "cursor_position": 50,
  "max_suggestions": 3
}
```

**Response:**
```json
{
  "suggestions": [
    {
      "text": "Запрос = Новый Запрос;\n    Запрос.Текст = \"SELECT * FROM Клиенты WHERE Код = &Код\";\n    Запрос.УстановитьПараметр(\"Код\", КодКлиента);",
      "confidence": 0.95,
      "type": "completion"
    },
    {
      "text": "Если НЕ ЗначениеЗаполнено(КодКлиента) Тогда\n        Возврат Неопределено;\n    КонецЕсли;",
      "confidence": 0.87,
      "type": "completion"
    }
  ],
  "processing_time_ms": 234
}
```

---

#### 2. Code Generation

**Endpoint:** `POST /api/v1/copilot/generate`

**Описание:** Генерация кода по описанию на русском языке.

**Request:**
```json
{
  "description": "Создай функцию для отправки email с вложением",
  "language": "bsl",
  "context": {
    "module_type": "common_module",
    "existing_functions": ["ОтправитьEmail", "ПолучитьНастройкиПочты"]
  }
}
```

**Response:**
```json
{
  "generated_code": "Функция ОтправитьEmailСВложением(Адресат, Тема, Текст, ПутьКФайлу) Экспорт\n    \n    Настройки = ПолучитьНастройкиПочты();\n    \n    Письмо = Новый ИнтернетПочтовоеСообщение;\n    Письмо.Кому.Добавить(Адресат);\n    Письмо.Тема = Тема;\n    Письмо.Тексты.Добавить(Текст, ТипТекстаПочтовогоСообщения.HTML);\n    \n    Если ЗначениеЗаполнено(ПутьКФайлу) Тогда\n        Вложение = Новый ИнтернетПочтовоеСообщениеВложение;\n        Вложение.Данные = Новый ДвоичныеДанные(ПутьКФайлу);\n        Письмо.Вложения.Добавить(Вложение);\n    КонецЕсли;\n    \n    Почта = Новый ИнтернетПочта;\n    Почта.Подключиться(Настройки);\n    Почта.Отправить(Письмо);\n    Почта.Отключиться();\n    \n    Возврат Истина;\n    \nКонецФункции",
  "explanation": "Функция отправляет email с вложением. Использует настройки почты из ПолучитьНастройкиПочты(), создает письмо с вложением и отправляет через ИнтернетПочта.",
  "confidence": 0.92
}
```

---

#### 3. Code Explanation

**Endpoint:** `POST /api/v1/copilot/explain`

**Описание:** Объяснение кода простым языком.

**Request:**
```json
{
  "code": "Запрос = Новый Запрос;\nЗапрос.Текст = \"SELECT T1.Номенклатура, SUM(T1.Количество) FROM ДокументОстатки T1 WHERE T1.Период BETWEEN &НачДата AND &КонДата GROUP BY T1.Номенклатура\";\nЗапрос.УстановитьПараметр(\"НачДата\", НачалоДня(ТекущаяДата()));\nЗапрос.УстановитьПараметр(\"КонДата\", КонецДня(ТекущаяДата()));",
  "language": "bsl",
  "detail_level": "beginner"
}
```

**Response:**
```json
{
  "explanation": {
    "summary": "Этот код создает SQL-запрос для получения остатков номенклатуры за текущий день.",
    "detailed": [
      "1. Создается новый объект Запрос для работы с базой данных",
      "2. В запросе выбираются номенклатура и сумма количества из таблицы ДокументОстатки",
      "3. Фильтруются записи за период с начала до конца текущего дня",
      "4. Результаты группируются по номенклатуре (чтобы получить сумму для каждой позиции)",
      "5. Параметры НачДата и КонДата устанавливаются как начало и конец текущего дня"
    ],
    "complexity": "medium",
    "potential_issues": [
      "Запрос может быть медленным на больших объемах данных - рекомендуется добавить индекс на поле Период"
    ]
  }
}
```

---

#### 4. Code Search

**Endpoint:** `POST /api/v1/copilot/search`

**Описание:** Семантический поиск по кодовой базе.

**Request:**
```json
{
  "query": "функция для расчета НДС",
  "language": "bsl",
  "max_results": 5,
  "search_scope": ["common_modules", "server_modules"]
}
```

**Response:**
```json
{
  "results": [
    {
      "file_path": "CommonModules/РаботаСНДС/Module.bsl",
      "function_name": "РассчитатьСуммуНДС",
      "code_snippet": "Функция РассчитатьСуммуНДС(Сумма, СтавкаНДС) Экспорт\n    Возврат Сумма * СтавкаНДС / 100;\nКонецФункции",
      "relevance_score": 0.95,
      "line_number": 15
    },
    {
      "file_path": "CommonModules/Финансы/Module.bsl",
      "function_name": "ВыделитьНДС",
      "code_snippet": "Функция ВыделитьНДС(СуммаСНДС, СтавкаНДС) Экспорт\n    Возврат СуммаСНДС * СтавкаНДС / (100 + СтавкаНДС);\nКонецФункции",
      "relevance_score": 0.88,
      "line_number": 42
    }
  ],
  "total_found": 2
}
```

---

## Примеры использования

### Пример 1: Автодополнение в IDE

```python
import httpx

async def get_code_completion(code: str, cursor_pos: int):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/copilot/complete",
            json={
                "code": code,
                "language": "bsl",
                "cursor_position": cursor_pos,
                "max_suggestions": 3
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        suggestions = response.json()["suggestions"]
        
        # Показать топ-3 предложения
        for i, suggestion in enumerate(suggestions, 1):
            print(f"{i}. {suggestion['text'][:50]}... (confidence: {suggestion['confidence']})")
        
        return suggestions

# Использование
code = "Функция ПолучитьДанные()\n    // "
suggestions = await get_code_completion(code, len(code))
```

### Пример 2: Генерация функции

```python
async def generate_function(description: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/copilot/generate",
            json={
                "description": description,
                "language": "bsl"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        result = response.json()
        
        print("Generated Code:")
        print(result["generated_code"])
        print("\nExplanation:")
        print(result["explanation"])
        
        return result

# Использование
await generate_function("Создай функцию для проверки ИНН")
```

### Пример 3: Объяснение сложного кода

```python
async def explain_code(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/copilot/explain",
            json={
                "code": code,
                "language": "bsl",
                "detail_level": "beginner"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        explanation = response.json()["explanation"]
        
        print(f"Summary: {explanation['summary']}\n")
        print("Detailed explanation:")
        for step in explanation['detailed']:
            print(f"  {step}")
        
        if explanation.get('potential_issues'):
            print("\n⚠️ Potential issues:")
            for issue in explanation['potential_issues']:
                print(f"  - {issue}")
        
        return explanation
```

---

## Интеграция

### VS Code Extension

```json
// settings.json
{
  "copilot.enable": true,
  "copilot.apiUrl": "http://localhost:8000/api/v1/copilot",
  "copilot.apiKey": "${env:COPILOT_API_KEY}",
  "copilot.languages": ["bsl", "javascript", "python"],
  "copilot.autoTrigger": true,
  "copilot.suggestionDelay": 300
}
```

### Cursor IDE Integration

```javascript
// Cursor extension
const copilot = {
  async getCompletion(code, position) {
    const response = await fetch('http://localhost:8000/api/v1/copilot/complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        code,
        cursor_position: position,
        language: 'bsl'
      })
    });
    
    return await response.json();
  }
};
```

---

## Best Practices

### 1. Оптимизация промптов

```python
# ❌ Плохо
description = "сделай функцию"

# ✅ Хорошо
description = """
Создай функцию для отправки уведомления пользователю.
Входные параметры:
- ИдентификаторПользователя (Строка)
- ТекстСообщения (Строка)
- ТипУведомления (Перечисление: Email, SMS, Push)

Функция должна:
1. Проверить существование пользователя
2. Получить контактные данные
3. Отправить уведомление через соответствующий сервис
4. Записать в лог результат отправки
"""
```

### 2. Использование контекста

```python
# Предоставляйте контекст для лучших результатов
context = {
    "module_type": "common_module",
    "existing_functions": ["ОтправитьEmail", "ОтправитьSMS"],
    "project_conventions": {
        "naming": "PascalCase",
        "error_handling": "try_catch",
        "logging": "structured"
    }
}

response = await client.post("/api/v1/copilot/generate", json={
    "description": description,
    "language": "bsl",
    "context": context
})
```

### 3. Валидация сгенерированного кода

```python
async def generate_and_validate(description: str):
    # Генерация
    generated = await generate_function(description)
    
    # Синтаксическая проверка
    syntax_check = await client.post("/api/v1/code_review/check_syntax", json={
        "code": generated["generated_code"],
        "language": "bsl"
    })
    
    if not syntax_check.json()["valid"]:
        print("⚠️ Syntax errors found!")
        return None
    
    # Проверка best practices
    quality_check = await client.post("/api/v1/code_review/analyze", json={
        "code": generated["generated_code"]
    })
    
    return {
        "code": generated["generated_code"],
        "quality_score": quality_check.json()["score"]
    }
```

---

## Troubleshooting

### Проблема: Медленные ответы

**Решение:**
```bash
# Включить кэширование
COPILOT_CACHE_TTL=3600

# Использовать более быструю модель
COPILOT_MODEL=gpt-3.5-turbo

# Или локальную модель
OLLAMA_MODEL=codellama:7b  # Вместо 13b
```

### Проблема: Низкое качество предложений

**Решение:**
```python
# Увеличить temperature для более креативных ответов
COPILOT_TEMPERATURE=0.7  # Вместо 0.2

# Или использовать более мощную модель
COPILOT_MODEL=gpt-4-turbo-preview
```

---

## FAQ

**Q: Поддерживается ли offline режим?**  
A: Да, используйте Ollama с локальными моделями (codellama, deepseek-coder).

**Q: Можно ли обучить Copilot на своем коде?**  
A: Да, используйте fine-tuning или RAG с вашей кодовой базой.

**Q: Какие языки поддерживаются?**  
A: BSL (1C), JavaScript, Python, SQL.

**Q: Безопасно ли отправлять код в Copilot?**  
A: Используйте локальные модели для конфиденциального кода.

---

**Версия документа:** 1.0  
**Последнее обновление:** 2025-11-27
