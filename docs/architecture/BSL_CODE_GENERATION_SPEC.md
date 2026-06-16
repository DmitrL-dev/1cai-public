# BSL Code Generation Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - специализация для BSL уникальна

---

## Обзор

**BSL Code Generation Standard** — детальная спецификация требований к генерации BSL кода AI агентами. Определяет стандарты качества, валидацию, best practices и метрики для AI-генерированного кода.

---

## 1. Требования к качеству

### 1.1 Синтаксис

**Обязательные требования:**

- 100% корректный синтаксис BSL
- Соответствие версии платформы 1C (8.2, 8.3.x)
- Корректное использование ключевых слов BSL (Функция, Процедура, КонецФункции, КонецПроцедуры)
- Правильная структура блоков (если...иначе...конецесли, для...конеццикла, попытка...исключение...конецпопытки)

**Валидация:**

```python
def validate_syntax(code: str) -> Dict[str, Any]:
    """
    Валидация синтаксиса BSL кода.
    
    Returns:
        {
            "valid": bool,
            "errors": List[str],
            "warnings": List[str],
        }
    """
```

### 1.2 Семантика

**Обязательные требования:**

- Корректное использование объектов метаданных
- Правильная работа с типами данных
- Корректная обработка ошибок (Попытка-Исключение)
- Правильное использование параметров функций/процедур

**Примеры ошибок:**

- ❌ Использование несуществующего объекта метаданных
- ❌ Неправильный тип данных (строку вместо числа)
- ❌ Отсутствие обработки ошибок в критических местах

### 1.3 Best Practices

**Критически важные:**

1. **Параметры запросов:**
   - ✅ Использовать параметры запросов вместо конкатенации строк
   - ❌ `Запрос.Текст = "SELECT * FROM Документ.Заказы WHERE Дата = '" + Дата + "'"`
   - ✅ `Запрос.УстановитьПараметр("Дата", Дата)`

2. **Кэширование метаданных:**
   - ✅ Кэшировать метаданные объектов в переменных
   - ❌ Многократное обращение к `Метаданные.Документы.Заказы`
   - ✅ `МетаданныеЗаказов = Метаданные.Документы.Заказы`

3. **Оптимизация запросов:**
   - ✅ Избегать запросов в циклах
   - ✅ Использовать временные таблицы для сложных запросов
   - ✅ Использовать индексы при работе с большими таблицами

4. **Обработка ошибок:**
   - ✅ Обрабатывать исключения в критических местах
   - ✅ Использовать `Попытка-Исключение` для внешних вызовов
   - ✅ Логировать ошибки

---

## 2. Формат результата генерации

### 2.1 Структура результата

```python
{
    "code": str,                    # Сгенерированный BSL код
    "explanation": str,             # Объяснение логики кода
    "quality_score": float,         # Оценка качества (0-1)
    "warnings": List[str],          # Предупреждения
    "metadata_used": List[str],     # Использованные объекты метаданных
    "functions": List[Dict],        # Список функций/процедур в коде
    "queries": List[Dict],          # SQL-запросы в коде
    "compliance": {
        "syntax": bool,             # Корректность синтаксиса
        "semantics": bool,          # Корректность семантики
        "best_practices": bool,     # Соответствие best practices
        "performance": bool,        # Оптимизация производительности
        "security": bool,           # Соответствие security стандартам
    },
    "metrics": {
        "loc": int,                 # Количество строк кода
        "complexity": int,          # Сложность кода
        "functions_count": int,     # Количество функций
        "queries_count": int,       # Количество запросов
    },
}
```

### 2.2 Структура функции

```python
{
    "name": str,                    # Имя функции
    "parameters": List[str],        # Параметры функции
    "return_type": str,             # Тип возвращаемого значения (опционально)
    "description": str,             # Описание функции
    "code": str,                    # Код функции
}
```

---

## 3. Валидация сгенерированного кода

### 3.1 Синтаксическая валидация

```python
def validate_syntax(code: str) -> Dict[str, Any]:
    """
    Валидация синтаксиса BSL кода.
    
    Использует BSL парсер (AST или regex-based) для проверки синтаксиса.
    """
    parser = BSLParser()
    try:
        parsed = parser.parse(code)
        return {
            "valid": True,
            "errors": [],
            "warnings": [],
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
        }
```

### 3.2 Семантическая валидация

```python
def validate_semantics(code: str, metadata: List[str]) -> Dict[str, Any]:
    """
    Валидация семантики BSL кода.
    
    Проверяет:
    - Использование объектов метаданных
    - Типы данных
    - Обработку ошибок
    """
    issues = []
    
    # Проверка использования метаданных
    for metadata_obj in extract_metadata_usage(code):
        if metadata_obj not in metadata:
            issues.append(f"Несуществующий объект метаданных: {metadata_obj}")
    
    # Проверка обработки ошибок
    if has_external_calls(code) and not has_error_handling(code):
        issues.append("Отсутствует обработка ошибок для внешних вызовов")
    
    return {
        "valid": len(issues) == 0,
        "errors": issues,
        "warnings": [],
    }
```

### 3.3 Best Practices валидация

```python
def validate_best_practices(code: str) -> Dict[str, Any]:
    """
    Валидация соответствия best practices.
    
    Проверяет:
    - Использование параметров запросов
    - Кэширование метаданных
    - Оптимизацию запросов
    """
    issues = []
    warnings = []
    
    # Проверка параметров запросов
    if has_string_concatenation_in_queries(code):
        issues.append("Использование конкатенации строк в запросах вместо параметров")
    
    # Проверка кэширования метаданных
    if has_repeated_metadata_access(code):
        warnings.append("Многократное обращение к метаданным без кэширования")
    
    # Проверка запросов в циклах
    if has_queries_in_loops(code):
        issues.append("Запросы к БД в циклах - оптимизировать через временные таблицы")
    
    return {
        "valid": len(issues) == 0,
        "errors": issues,
        "warnings": warnings,
    }
```

---

## 4. Метрики качества

### 4.1 Оценка качества кода

```python
def calculate_quality_score(code: str, metadata: List[str]) -> float:
    """
    Расчет общей оценки качества кода (0-1).
    
    Учитывает:
    - Синтаксис (вес: 0.3)
    - Семантику (вес: 0.3)
    - Best practices (вес: 0.2)
    - Производительность (вес: 0.1)
    - Безопасность (вес: 0.1)
    """
    syntax_result = validate_syntax(code)
    semantics_result = validate_semantics(code, metadata)
    best_practices_result = validate_best_practices(code)
    
    syntax_score = 1.0 if syntax_result["valid"] else 0.0
    semantics_score = 1.0 if semantics_result["valid"] else 0.5
    best_practices_score = 1.0 if best_practices_result["valid"] else 0.7
    
    # Производительность и безопасность (упрощенная оценка)
    performance_score = 0.9 if not has_queries_in_loops(code) else 0.5
    security_score = 1.0 if has_parameterized_queries(code) else 0.0
    
    total_score = (
        syntax_score * 0.3 +
        semantics_score * 0.3 +
        best_practices_score * 0.2 +
        performance_score * 0.1 +
        security_score * 0.1
    )
    
    return total_score
```

### 4.2 Метрики кода

```python
def calculate_metrics(code: str) -> Dict[str, Any]:
    """
    Расчет метрик кода.
    
    Returns:
        {
            "loc": int,              # Строк кода
            "complexity": int,       # Сложность (цикломатическая)
            "functions_count": int,  # Количество функций
            "queries_count": int,    # Количество запросов
            "variables_count": int,  # Количество переменных
        }
    """
    parser = BSLParser()
    parsed = parser.parse(code)
    
    return {
        "loc": parsed.get("loc", 0),
        "complexity": parsed.get("total_complexity", 0),
        "functions_count": len(parsed.get("functions", [])),
        "queries_count": len(parsed.get("queries", [])),
        "variables_count": len(parsed.get("variables", [])),
    }
```

---

## 5. Примеры генерации

### 5.1 Простая функция

**Запрос:** "Создай функцию для расчета НДС"

**Результат:**

```bsl
///
/// Рассчитывает НДС от суммы
/// @param Сумма - Сумма без НДС
/// @param СтавкаНДС - Ставка НДС (по умолчанию 20)
/// @return НДС
///
Функция РассчитатьНДС(Сумма, СтавкаНДС = 20) Экспорт
    
    Если Сумма <= 0 Тогда
        ВызватьИсключение "Сумма должна быть больше нуля";
    КонецЕсли;
    
    Если СтавкаНДС <= 0 Или СтавкаНДС >= 100 Тогда
        ВызватьИсключение "Ставка НДС должна быть от 0 до 100";
    КонецЕсли;
    
    Возврат Окр(Сумма * СтавкаНДС / 100, 2);
    
КонецФункции
```

**Метрики:**

```python
{
    "code": "...",
    "quality_score": 0.95,
    "compliance": {
        "syntax": True,
        "semantics": True,
        "best_practices": True,
        "performance": True,
        "security": True,
    },
    "metrics": {
        "loc": 12,
        "complexity": 3,
        "functions_count": 1,
    },
}
```

### 5.2 Функция с запросом

**Запрос:** "Создай функцию для получения заказов за период"

**Результат:**

```bsl
///
/// Получает заказы покупателей за период
/// @param ДатаНачала - Дата начала периода
/// @param ДатаОкончания - Дата окончания периода
/// @return ТаблицаЗначений с заказами
///
Функция ПолучитьЗаказыЗаПериод(ДатаНачала, ДатаОкончания) Экспорт
    
    Запрос = Новый Запрос;
    Запрос.Текст = 
        "ВЫБРАТЬ
        |    ЗаказыПокупателей.Ссылка,
        |    ЗаказыПокупателей.Дата,
        |    ЗаказыПокупателей.СуммаДокумента
        |ИЗ
        |    Документ.ЗаказыПокупателей КАК ЗаказыПокупателей
        |ГДЕ
        |    ЗаказыПокупателей.Дата >= &ДатаНачала
        |    И ЗаказыПокупателей.Дата <= &ДатаОкончания";
    
    Запрос.УстановитьПараметр("ДатаНачала", ДатаНачала);
    Запрос.УстановитьПараметр("ДатаОкончания", ДатаОкончания);
    
    Результат = Запрос.Выполнить();
    Возврат Результат.Выгрузить();
    
КонецФункции
```

---

## 6. Интеграция с AI агентами

### 6.1 Интерфейс генерации

```python
class BSLCodeGenerator:
    """Генератор BSL кода."""
    
    async def generate(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Генерация BSL кода по описанию.
        
        Args:
            prompt: Описание требуемого кода
            context: Контекст (метаданные, существующий код и т.п.)
        
        Returns:
            Результат генерации в формате BSL_CODE_GENERATION_SPEC
        """
        # 1. Генерация кода через LLM
        code = await self._generate_code(prompt, context)
        
        # 2. Валидация
        syntax_result = validate_syntax(code)
        semantics_result = validate_semantics(code, context.get("metadata", []))
        best_practices_result = validate_best_practices(code)
        
        # 3. Расчет метрик
        quality_score = calculate_quality_score(code, context.get("metadata", []))
        metrics = calculate_metrics(code)
        
        # 4. Формирование результата
        return {
            "code": code,
            "explanation": self._generate_explanation(code),
            "quality_score": quality_score,
            "warnings": best_practices_result.get("warnings", []),
            "metadata_used": extract_metadata_usage(code),
            "functions": extract_functions(code),
            "queries": extract_queries(code),
            "compliance": {
                "syntax": syntax_result["valid"],
                "semantics": semantics_result["valid"],
                "best_practices": best_practices_result["valid"],
                "performance": not has_queries_in_loops(code),
                "security": has_parameterized_queries(code),
            },
            "metrics": metrics,
        }
```

---

## 7. JSON Schema для результатов генерации

См. `BSL_AI_AGENT_RESULT_SCHEMA.json` для детальной схемы.

---

## 8. Следующие шаги

1. **Реализация валидаторов** — создание валидаторов для всех проверок
2. **Интеграция с AI агентами** — обновление существующих агентов для соответствия стандарту
3. **Тестирование** — создание тестовых случаев для различных сценариев генерации

---

**Примечание:** Этот стандарт обеспечивает единообразие и высокое качество AI-генерированного BSL кода.

