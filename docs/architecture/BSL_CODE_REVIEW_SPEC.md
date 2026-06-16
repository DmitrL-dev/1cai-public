# BSL Code Review Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - специализация для BSL уникальна

---

## Обзор

**BSL Code Review Standard** — детальная спецификация требований к автоматическому ревью BSL кода AI агентами. Определяет категории проверок, checklist, форматы результатов и интеграцию с 1C-специфичными проверками.

---

## 1. Категории проверок

### 1.1 Security (Безопасность)

**Критичные проблемы:**

- SQL Injection (конкатенация строк в запросах)
- XSS (неэкранированный вывод)
- Небезопасный доступ к данным (отсутствие проверки прав)

**Проверки:**

```python
def check_security(code: str) -> List[Dict[str, Any]]:
    """
    Проверка безопасности BSL кода.
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    
    # SQL Injection
    if has_string_concatenation_in_queries(code):
        issues.append({
            "severity": "critical",
            "category": "security",
            "message": "Использование конкатенации строк в запросах - риск SQL injection",
            "line": find_line_with_concatenation(code),
            "suggestion": "Использовать параметры запросов: Запрос.УстановитьПараметр()",
        })
    
    # XSS
    if has_unescaped_output(code):
        issues.append({
            "severity": "high",
            "category": "security",
            "message": "Неэкранированный вывод - риск XSS",
            "line": find_line_with_output(code),
            "suggestion": "Использовать Строка() или HTMLEncode() для экранирования",
        })
    
    # Доступ к данным
    if has_data_access_without_permission_check(code):
        issues.append({
            "severity": "high",
            "category": "security",
            "message": "Отсутствует проверка прав доступа перед операциями с данными",
            "line": find_line_with_data_access(code),
            "suggestion": "Добавить проверку прав: ПроверитьПрава() или ПраваПользователя()",
        })
    
    return issues
```

### 1.2 Performance (Производительность)

**Критичные проблемы:**

- Запросы к БД в циклах
- N+1 проблема в запросах
- Отсутствие кэширования метаданных
- Неоптимальные запросы (отсутствие индексов)

**Проверки:**

```python
def check_performance(code: str) -> List[Dict[str, Any]]:
    """
    Проверка производительности BSL кода.
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    
    # Запросы в циклах
    if has_queries_in_loops(code):
        issues.append({
            "severity": "high",
            "category": "performance",
            "message": "Запросы к БД в циклах - критично для производительности",
            "line": find_line_with_query_in_loop(code),
            "suggestion": "Вынести запрос из цикла, использовать временную таблицу",
        })
    
    # N+1 проблема
    if has_n_plus_one_pattern(code):
        issues.append({
            "severity": "medium",
            "category": "performance",
            "message": "N+1 проблема в запросах - множественные запросы для связанных данных",
            "line": find_line_with_n_plus_one(code),
            "suggestion": "Использовать JOIN или подзапросы для получения всех данных за один запрос",
        })
    
    # Кэширование метаданных
    if has_repeated_metadata_access(code):
        issues.append({
            "severity": "medium",
            "category": "performance",
            "message": "Многократное обращение к метаданным без кэширования",
            "line": find_line_with_metadata_access(code),
            "suggestion": "Кэшировать метаданные в переменной: МетаданныеОбъекта = Метаданные.Документы.Заказы",
        })
    
    return issues
```

### 1.3 Best Practices (Лучшие практики)

**Проверки:**

```python
def check_best_practices(code: str) -> List[Dict[str, Any]]:
    """
    Проверка соответствия best practices BSL.
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    
    # Использование ПроверитьТип() вместо Тип()
    if has_type_check_without_validate(code):
        issues.append({
            "severity": "low",
            "category": "best_practices",
            "message": "Использование Тип() вместо ПроверитьТип() - менее надежно",
            "line": find_line_with_type_check(code),
            "suggestion": "Использовать ПроверитьТип() для проверки типа объекта",
        })
    
    # Обработка исключений
    if has_external_calls_without_error_handling(code):
        issues.append({
            "severity": "medium",
            "category": "best_practices",
            "message": "Отсутствует обработка исключений для внешних вызовов",
            "line": find_line_with_external_call(code),
            "suggestion": "Обернуть в блок Попытка-Исключение",
        })
    
    # Документация
    if has_undocumented_exported_functions(code):
        issues.append({
            "severity": "low",
            "category": "best_practices",
            "message": "Экспортируемая функция без документации",
            "line": find_line_with_function(code),
            "suggestion": "Добавить комментарии с описанием функции и параметров",
        })
    
    return issues
```

### 1.4 1C-Specific (Специфика 1C)

**Проверки:**

```python
def check_1c_specific(code: str) -> List[Dict[str, Any]]:
    """
    Проверка 1C-специфичных проблем.
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    
    # Использование объектов метаданных
    if has_invalid_metadata_usage(code):
        issues.append({
            "severity": "high",
            "category": "1c_specific",
            "message": "Использование несуществующего объекта метаданных",
            "line": find_line_with_metadata(code),
            "suggestion": "Проверить правильность пути к объекту метаданных",
        })
    
    # Работа с регистрами
    if has_incorrect_register_usage(code):
        issues.append({
            "severity": "medium",
            "category": "1c_specific",
            "message": "Некорректное использование регистра - проверьте измеряния и ресурсы",
            "line": find_line_with_register(code),
            "suggestion": "Убедитесь, что все измеряния заполнены и ресурсы корректны",
        })
    
    # Оптимизация запросов
    if has_unoptimized_query(code):
        issues.append({
            "severity": "medium",
            "category": "1c_specific",
            "message": "Запрос может быть оптимизирован через индексы или временные таблицы",
            "line": find_line_with_query(code),
            "suggestion": "Добавить индексы или использовать временные таблицы для больших объемов данных",
        })
    
    return issues
```

---

## 2. Checklist для автоматического ревью

### 2.1 Полный checklist

```python
REVIEW_CHECKLIST = {
    "security": [
        "sql_injection",           # Конкатенация строк в запросах
        "xss",                     # Неэкранированный вывод
        "access_control",          # Проверка прав доступа
        "sensitive_data",          # Обработка чувствительных данных
    ],
    "performance": [
        "queries_in_loops",        # Запросы в циклах
        "n_plus_one",              # N+1 проблема
        "metadata_caching",        # Кэширование метаданных
        "query_optimization",      # Оптимизация запросов
    ],
    "best_practices": [
        "type_checking",           # Использование ПроверитьТип()
        "error_handling",          # Обработка исключений
        "documentation",           # Документация кода
        "naming_conventions",      # Соглашения об именовании
    ],
    "1c_specific": [
        "metadata_usage",          # Использование объектов метаданных
        "register_usage",          # Работа с регистрами
        "form_handling",           # Работа с формами
        "query_optimization_1c",   # Оптимизация запросов 1C
    ],
}
```

### 2.2 Приоритизация проверок

```python
def prioritize_checks(context: Dict[str, Any]) -> List[str]:
    """
    Определение приоритета проверок на основе контекста.
    
    Args:
        context: Контекст (тип модуля, объект метаданных и т.п.)
    
    Returns:
        Список проверок в порядке приоритета
    """
    module_type = context.get("module_type", "unknown")
    metadata_type = context.get("metadata_type", "unknown")
    
    checks = []
    
    # Всегда проверяем security
    checks.extend(REVIEW_CHECKLIST["security"])
    
    # Для ObjectModule проверяем performance
    if module_type == "ObjectModule":
        checks.extend(REVIEW_CHECKLIST["performance"])
    
    # Для модулей с регистрами проверяем 1C-specific
    if metadata_type in ["RegisterInformation", "RegisterAccumulation", "RegisterAccounting"]:
        checks.extend(REVIEW_CHECKLIST["1c_specific"])
    
    # Всегда проверяем best practices
    checks.extend(REVIEW_CHECKLIST["best_practices"])
    
    return checks
```

---

## 3. Формат результата ревью

### 3.1 Структура результата

```python
{
    "issues": List[Dict],           # Найденные проблемы
    "suggestions": List[Dict],       # Предложения по улучшению
    "quality_score": float,         # Оценка качества (0-1)
    "compliance": {
        "security": bool,           # Соответствие security стандартам
        "performance": bool,        # Соответствие performance стандартам
        "best_practices": bool,     # Соответствие best practices
        "1c_specific": bool,        # Соответствие 1C-специфичным стандартам
    },
    "metrics": {
        "complexity": int,          # Сложность кода
        "loc": int,                 # Количество строк
        "functions_count": int,     # Количество функций
        "issues_count": int,        # Количество проблем
    },
}
```

### 3.2 Структура проблемы

```python
{
    "severity": str,                # "critical"|"high"|"medium"|"low"
    "category": str,                # "security"|"performance"|"best_practices"|"1c_specific"
    "message": str,                 # Описание проблемы
    "line": int,                    # Номер строки (опционально)
    "suggestion": str,             # Предложение по исправлению
    "code": str,                    # Проблемный код (опционально)
    "fixed_code": str,              # Исправленный код (опционально)
}
```

### 3.3 Структура предложения

```python
{
    "type": str,                    # "refactor"|"optimize"|"document"|"test"
    "message": str,                 # Описание предложения
    "line": int,                    # Номер строки (опционально)
    "code": str,                    # Пример улучшенного кода (опционально)
    "priority": str,                # "high"|"medium"|"low"
}
```

---

## 4. Интеграция с 1C специфичными проверками

### 4.1 Проверка метаданных

```python
def validate_metadata_usage(code: str, available_metadata: List[str]) -> List[Dict]:
    """
    Проверка использования объектов метаданных.
    
    Args:
        code: BSL код
        available_metadata: Список доступных объектов метаданных
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    used_metadata = extract_metadata_usage(code)
    
    for metadata_obj in used_metadata:
        if metadata_obj not in available_metadata:
            issues.append({
                "severity": "high",
                "category": "1c_specific",
                "message": f"Использование несуществующего объекта метаданных: {metadata_obj}",
                "line": find_line_with_metadata(code, metadata_obj),
                "suggestion": f"Проверьте правильность пути к объекту метаданных или добавьте {metadata_obj} в конфигурацию",
            })
    
    return issues
```

### 4.2 Проверка работы с регистрами

```python
def validate_register_usage(code: str) -> List[Dict]:
    """
    Проверка работы с регистрами.
    
    Returns:
        List[Dict] с найденными проблемами
    """
    issues = []
    
    # Проверка заполнения измеряний
    if has_register_write_without_dimensions(code):
        issues.append({
            "severity": "high",
            "category": "1c_specific",
            "message": "Запись в регистр без заполнения всех измеряний",
            "line": find_line_with_register_write(code),
            "suggestion": "Убедитесь, что все измеряния регистра заполнены",
        })
    
    # Проверка работы с ресурсами
    if has_incorrect_resource_usage(code):
        issues.append({
            "severity": "medium",
            "category": "1c_specific",
            "message": "Некорректное использование ресурсов регистра",
            "line": find_line_with_resource(code),
            "suggestion": "Проверьте правильность работы с ресурсами (применение, получение остатков)",
        })
    
    return issues
```

---

## 5. Примеры ревью

### 5.1 Пример с SQL Injection

**Код:**

```bsl
Функция ПолучитьЗаказы(ДатаНачала, ДатаОкончания) Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "SELECT * FROM Документ.ЗаказыПокупателей WHERE Дата >= '" + ДатаНачала + "' AND Дата <= '" + ДатаОкончания + "'";
    Возврат Запрос.Выполнить();
КонецФункции
```

**Результат ревью:**

```python
{
    "issues": [
        {
            "severity": "critical",
            "category": "security",
            "message": "Использование конкатенации строк в запросах - риск SQL injection",
            "line": 3,
            "suggestion": "Использовать параметры запросов: Запрос.УстановитьПараметр(\"ДатаНачала\", ДатаНачала)",
            "code": "Запрос.Текст = \"SELECT * FROM Документ.ЗаказыПокупателей WHERE Дата >= '\" + ДатаНачала + \"' AND Дата <= '\" + ДатаОкончания + \"'\"",
            "fixed_code": "Запрос.Текст = \"SELECT * FROM Документ.ЗаказыПокупателей WHERE Дата >= &ДатаНачала AND Дата <= &ДатаОкончания\";\nЗапрос.УстановитьПараметр(\"ДатаНачала\", ДатаНачала);\nЗапрос.УстановитьПараметр(\"ДатаОкончания\", ДатаОкончания);",
        }
    ],
    "quality_score": 0.3,
    "compliance": {
        "security": False,
        "performance": True,
        "best_practices": False,
        "1c_specific": True,
    },
}
```

---

## 6. JSON Schema для результатов ревью

См. `BSL_AI_AGENT_RESULT_SCHEMA.json` для детальной схемы.

---

## 7. Следующие шаги

1. **Реализация проверок** — создание всех проверок из checklist
2. **Интеграция с AI агентами** — обновление существующих агентов для соответствия стандарту
3. **Тестирование** — создание тестовых случаев для различных сценариев ревью

---

**Примечание:** Этот стандарт обеспечивает единообразие и полноту автоматического ревью BSL кода.

