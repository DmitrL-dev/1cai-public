# BSL Parser Standard

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - стандарт для парсеров BSL уникален

---

## Обзор

**BSL Parser Standard** — формальная спецификация требований к парсерам BSL кода для интеграции с BSL Code Graph Standard. Определяет интерфейсы, метаданные и требования к качеству парсинга.

### Цель:

Обеспечить совместимость различных парсеров BSL (AST-based, regex-based, neural) с BSL Code Graph Builder и другими компонентами платформы.

---

## 1. Интерфейс парсера

### 1.1 Базовый интерфейс

Все парсеры BSL должны реализовывать следующий интерфейс:

```python
class BSLParserInterface:
    """Базовый интерфейс для всех парсеров BSL."""
    
    def parse(self, code: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Парсинг BSL кода.
        
        Args:
            code: BSL код для парсинга
            file_path: Путь к файлу (опционально, для контекста)
        
        Returns:
            Словарь с результатами парсинга (см. раздел 2)
        """
        raise NotImplementedError
```

### 1.2 Обязательные методы

- `parse(code: str, file_path: Optional[str] = None) -> Dict[str, Any]` — основной метод парсинга
- Опционально: `parse_file(file_path: str) -> Dict[str, Any]` — парсинг из файла

---

## 2. Формат результата парсинга

### 2.1 Обязательные поля

Результат `parse()` должен возвращать словарь со следующими обязательными полями:

```python
{
    "functions": List[Dict[str, Any]],      # Список функций
    "procedures": List[Dict[str, Any]],      # Список процедур
    "variables": List[Dict[str, Any]],       # Список переменных (опционально)
    "queries": List[Dict[str, Any]],        # Список SQL-запросов (опционально)
    "loc": int,                             # Количество строк кода
    "total_complexity": int,                # Общая сложность модуля
}
```

### 2.2 Структура функции/процедуры

```python
{
    "name": str,                    # Имя функции/процедуры
    "parameters": List[str],         # Список параметров
    "is_export": bool,              # Экспортируемая ли функция
    "exported": bool,               # Альтернативное поле (совместимость)
    "body": str,                    # Тело функции/процедуры
    "start_line": int,              # Начальная строка
    "end_line": int,                # Конечная строка
    "line_start": int,              # Альтернативное поле (совместимость)
    "line_end": int,                # Альтернативное поле (совместимость)
    "complexity": int,              # Сложность функции (цикломатическая)
    "has_documentation": bool,     # Есть ли документация (комментарии)
}
```

### 2.3 Структура переменной

```python
{
    "name": str,                    # Имя переменной
    "type": str,                    # Тип переменной (опционально)
    "scope": str,                   # Область видимости (global/local)
    "line": int,                    # Строка объявления
}
```

### 2.4 Структура запроса

```python
{
    "text": str,                    # Текст SQL-запроса
    "type": str,                    # Тип запроса (SELECT/INSERT/UPDATE/DELETE)
    "line": int,                    # Строка, где найден запрос
    "tables_used": List[str],       # Список используемых таблиц (опционально)
}
```

---

## 3. Типы парсеров

### 3.1 AST Parser (предпочтительно)

**Требования:**

- Использование bsl-language-server или аналогичного AST парсера
- Полная поддержка синтаксиса BSL
- Извлечение семантической информации (типы, области видимости)
- Поддержка всех версий BSL (8.2, 8.3.x)

**Пример реализации:**

```python
from scripts.parsers.bsl_ast_parser import BSLASTParser

parser = BSLASTParser(use_language_server=True)
result = parser.parse(code)
```

### 3.2 Regex-based Parser (fallback)

**Требования:**

- Базовая поддержка функций, процедур, переменных
- Извлечение SQL-запросов
- Минимальная поддержка сложности кода

**Пример реализации:**

```python
from src.ai.agents.code_review.bsl_parser import BSLParser

parser = BSLParser()
result = parser.parse(code)
```

### 3.3 Neural Parser (экспериментально)

**Требования:**

- Использование нейросетевых моделей для парсинга
- Высокая точность извлечения структуры
- Поддержка нестандартных конструкций

**Пример реализации:**

```python
from scripts.parsers.neural.neural_bsl_parser import NeuralBSLParser

parser = NeuralBSLParser()
result = parser.parse(code)
```

---

## 4. Метаданные для BSL артефактов

### 4.1 Модуль

```python
{
    "module_path": str,             # Путь к модулю (например, "ОбщийМодуль.УправлениеЗаказами")
    "module_type": str,             # Тип модуля (ObjectModule, ManagerModule, FormModule, CommonModule)
    "loc": int,                     # Количество строк кода
    "complexity": int,               # Общая сложность модуля
    "functions_count": int,         # Количество функций
    "procedures_count": int,        # Количество процедур
    "exported_functions": List[str], # Список экспортируемых функций
}
```

### 4.2 Функция/Процедура

```python
{
    "function_name": str,           # Имя функции/процедуры
    "module": str,                  # Модуль, к которому принадлежит
    "exported": bool,               # Экспортируемая ли
    "parameters": List[str],         # Список параметров
    "complexity": int,               # Сложность функции
    "start_line": int,              # Начальная строка
    "end_line": int,                # Конечная строка
    "has_documentation": bool,      # Есть ли документация
    "calls_functions": List[str],   # Список вызываемых функций (опционально)
    "uses_tables": List[str],       # Список используемых таблиц (опционально)
    "uses_metadata": List[str],      # Список используемых объектов метаданных (опционально)
}
```

---

## 5. Требования к качеству парсинга

### 5.1 Точность

- **Функции/Процедуры:** 95%+ точность извлечения
- **Параметры:** 90%+ точность извлечения
- **SQL-запросы:** 85%+ точность извлечения
- **Сложность:** 80%+ точность расчета

### 5.2 Производительность

- **AST Parser:** < 1 секунда на модуль (1000 строк)
- **Regex Parser:** < 0.1 секунды на модуль (1000 строк)
- **Neural Parser:** < 5 секунд на модуль (1000 строк)

### 5.3 Обработка ошибок

- Парсер должен обрабатывать синтаксические ошибки gracefully
- Возвращать частичные результаты при ошибках
- Логировать ошибки парсинга

---

## 6. Интеграция с BSL Code Graph Builder

### 6.1 Использование парсера

```python
from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder
from src.ai.code_graph import InMemoryCodeGraphBackend

backend = InMemoryCodeGraphBackend()
builder = OneCCodeGraphBuilder(backend, use_ast_parser=True)

# Парсер выбирается автоматически:
# 1. AST Parser (если доступен)
# 2. Regex Parser (fallback)
```

### 6.2 Кастомный парсер

```python
class CustomBSLParser:
    def parse(self, code: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        # Реализация парсинга
        return {
            "functions": [...],
            "procedures": [...],
            "loc": 100,
            "total_complexity": 10,
        }

# Использование кастомного парсера
builder = OneCCodeGraphBuilder(backend)
builder._parser = CustomBSLParser()
```

---

## 7. Примеры использования

### 7.1 Базовый парсинг

```python
from src.ai.agents.code_review.bsl_parser import BSLParser

parser = BSLParser()
code = """
Функция Тест() Экспорт
    Возврат Истина;
КонецФункции
"""

result = parser.parse(code)
print(result["functions"])  # [{"name": "Тест", ...}]
```

### 7.2 AST парсинг

```python
from scripts.parsers.bsl_ast_parser import BSLASTParser

parser = BSLASTParser(use_language_server=True)
result = parser.parse(code, file_path="module.bsl")
```

### 7.3 Интеграция с графом

```python
from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder
from src.ai.code_graph import InMemoryCodeGraphBackend

backend = InMemoryCodeGraphBackend()
builder = OneCCodeGraphBuilder(backend, use_ast_parser=True)

stats = await builder.build_from_module(
    "ОбщийМодуль.Тест",
    code,
    module_metadata={"owner": "my-team"},
)
```

---

## 8. Валидация парсера

### 8.1 Тесты соответствия

Парсер должен проходить следующие тесты:

1. **Извлечение функций:** все функции из тестового модуля должны быть найдены
2. **Извлечение процедур:** все процедуры из тестового модуля должны быть найдены
3. **Параметры:** параметры функций должны быть извлечены корректно
4. **Сложность:** расчет сложности должен быть близок к эталонному значению
5. **SQL-запросы:** все SQL-запросы должны быть найдены

### 8.2 Тестовые модули

Тестовые модули для валидации находятся в `tests/fixtures/bsl_parser/`:

- `simple_module.bsl` — простой модуль с функциями и процедурами
- `complex_module.bsl` — сложный модуль с запросами и метаданными
- `edge_cases.bsl` — граничные случаи (динамические вызовы, вложенные функции)

---

## 9. Расширяемость

### 9.1 Добавление новых полей

Парсеры могут добавлять дополнительные поля в результат парсинга:

```python
{
    "functions": [...],
    "procedures": [...],
    "loc": 100,
    "total_complexity": 10,
    # Дополнительные поля
    "ast": AST,                    # AST дерево (для AST парсеров)
    "semantic_info": Dict,         # Семантическая информация
    "warnings": List[str],          # Предупреждения парсинга
}
```

### 9.2 Плагины парсеров

Парсеры могут быть расширены через плагины:

```python
class ParserPlugin:
    def process_ast(self, ast: AST) -> Dict[str, Any]:
        """Обработка AST для извлечения дополнительной информации."""
        pass
```

---

## 10. Совместимость

### 10.1 Обратная совместимость

Парсеры должны поддерживать обратную совместимость:

- Старые поля (`line_start`, `line_end`) должны работать наряду с новыми (`start_line`, `end_line`)
- Поле `is_export` должно работать наряду с `exported`

### 10.2 Версионирование

Парсеры должны указывать версию в метаданных:

```python
{
    "parser_version": "1.0.0",
    "parser_type": "ast|regex|neural",
    ...
}
```

---

## 11. Рекомендации по реализации

### 11.1 AST Parser

- Использовать bsl-language-server для максимальной точности
- Кэшировать результаты парсинга для производительности
- Обрабатывать ошибки парсинга gracefully

### 11.2 Regex Parser

- Использовать регулярные выражения для базового парсинга
- Добавлять эвристики для улучшения точности
- Поддерживать fallback для сложных случаев

### 11.3 Neural Parser

- Обучать модели на большом датасете BSL кода
- Использовать transfer learning для улучшения точности
- Комбинировать с AST/Regex парсерами для надежности

---

## 12. Следующие шаги

1. **Реализация валидаторов** — создание тестов для проверки соответствия парсеров стандарту
2. **Документация примеров** — добавление примеров использования различных парсеров
3. **Интеграция с CI** — автоматическая проверка соответствия парсеров стандарту в CI

---

**Примечание:** Этот стандарт обеспечивает совместимость различных парсеров BSL с BSL Code Graph Builder и другими компонентами платформы, делая систему расширяемой и гибкой.

