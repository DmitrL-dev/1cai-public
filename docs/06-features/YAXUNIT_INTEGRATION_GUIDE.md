# YAxUnit Integration Guide

> **Статус:** ✅ Полностью интегрировано  
> **Версия:** 1.0.0  
> **Дата:** 2025-01-17

---

## Обзор

YAxUnit полностью интегрирован в проект 1C AI Stack для тестирования BSL кода и AI-сгенерированных модулей.

---

## 📜 Авторы и лицензия

**YAxUnit** разработан и поддерживается компанией **[BIA-Technologies Limited Liability Company](http://bia-tech.ru/)**.

- **Автор:** BIA-Technologies Limited Liability Company
- **Лицензия:** [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0.html)
- **Репозиторий:** [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit)
- **Документация:** [https://bia-technologies.github.io/yaxunit/](https://bia-technologies.github.io/yaxunit/)
- **Copyright:** © 2021-2025 BIA-Technologies Limited Liability Company

### 🙏 Благодарности

Мы выражаем благодарность команде **BIA-Technologies** за создание и поддержку отличного фреймворка для тестирования BSL кода.

YAxUnit является важной частью экосистемы open-source для 1С:Предприятие и значительно упрощает процесс тестирования BSL кода.

---

## Установка

### 1. Структура проекта

YAxUnit установлен в `tools/yaxunit/`:

```
tools/yaxunit/
├── src/                    # Исходный код расширения YAxUnit
│   └── CommonModules/      # Общие модули YAxUnit
└── README.md              # Документация
```

### 2. Требования

- 1С:Предприятие 8.3.10 или старше
- YAxUnit расширение загружено в информационную базу
- Python 3.11+
- OneScript (опционально, для альтернативного запуска)

### 3. Настройка информационной базы

Для запуска тестов необходимо настроить информационную базу:

```bash
# Через переменные окружения
export V8_IB_PATH="/path/to/test/database"
export V8_IB_USER="Admin"
export V8_IB_PASSWORD="password"

# Или через параметры скрипта
python scripts/tests/run_yaxunit_tests.py \
    --ib-path "/path/to/test/database" \
    --ib-user "Admin" \
    --ib-password "password"
```

## Использование

### Запуск тестов

#### Через Makefile

```bash
make test-bsl
```

#### Напрямую через скрипт

```bash
# Все тесты
python scripts/tests/run_bsl_tests.py

# Конкретный тест
python scripts/tests/run_yaxunit_tests.py \
    --test-files test_ai_generated_code.bsl \
    --ib-path "/path/to/ib"
```

### Структура тестов

Тесты находятся в `tests/bsl/`:

```
tests/bsl/
├── test_ai_generated_code.bsl  # Тесты для AI-сгенерированного кода
├── test_parsers.bsl             # Тесты для парсеров
├── test_integrations.bsl       # Тесты для интеграций
├── test_mcp_tools.bsl          # Тесты для MCP инструментов
└── testplan.json               # Конфигурация тестов
```

### Пример теста

```bsl
// Тест: AI-сгенерированная функция расчета скидки
Процедура Тест_AIГенерация_ФункцияРассчетаСкидки() Экспорт
    
    // Arrange (подготовка)
    УровеньЛояльности = "Gold";
    Сумма = 1000;
    ОжидаемаяСкидка = 100; // 10% для Gold
    
    // Act (действие)
    Результат = РассчитатьСкидку(УровеньЛояльности, Сумма);
    
    // Assert (проверка через YAxUnit)
    ЮТест.ОжидаетЧто(Результат, "Результат расчета скидки")
        .Заполнено()
        .ИмеетТип("Число")
        .Равно(ОжидаемаяСкидка)
        .Больше(0);
    
КонецПроцедуры
```

## Автоматическая валидация AI-кода

### Использование AICodeValidator

```python
from src.services.ai_code_validator import AICodeValidator

# Инициализация валидатора
validator = AICodeValidator(
    test_output_dir=Path("output/bsl-tests"),
    ib_path="/path/to/test/database",
    ib_user="Admin",
)

# Валидация сгенерированного кода
result = await validator.validate_generated_code(
    generated_code="""
    Функция РассчитатьСкидку(УровеньЛояльности, Сумма)
        Если УровеньЛояльности = "Gold" Тогда
            Возврат Сумма * 0.1;
        Иначе
            Возврат 0;
        КонецЕсли;
    КонецФункции
    """,
    function_name="РассчитатьСкидку",
    auto_run=True,  # Автоматически запускать тесты
)

# Проверка результата
if result.success:
    print(f"✅ Тесты пройдены: {result.passed_tests}/{result.test_count}")
else:
    print(f"❌ Тесты провалены: {result.failed_tests} ошибок")
    for error in result.errors:
        print(f"  - {error}")
```

### Интеграция в pipeline генерации

```python
from src.services.ai_code_validator import AICodeValidator

async def generate_and_validate_code(prompt: str):
    """Генерация кода с автоматической валидацией"""
    
    # 1. Генерация кода через AI
    generated_code = await ai_agent.generate_bsl_code(prompt)
    
    # 2. Валидация через YAxUnit
    validator = AICodeValidator(ib_path=TEST_IB_PATH)
    validation_result = await validator.validate_generated_code(
        generated_code=generated_code.code,
        function_name=generated_code.function_name,
        auto_run=True,
    )
    
    # 3. Проверка результата
    if not validation_result.success:
        # Код не прошел тесты - отправляем на доработку
        return {
            "status": "validation_failed",
            "code": generated_code.code,
            "errors": validation_result.errors,
            "test_file": validation_result.test_file_path,
        }
    
    # 4. Код прошел тесты - можно использовать
    return {
        "status": "success",
        "code": generated_code.code,
        "test_count": validation_result.test_count,
        "passed_tests": validation_result.passed_tests,
    }
```

## CI/CD интеграция

### GitHub Actions

Тесты автоматически запускаются в CI через job `bsl-tests`:

```yaml
bsl-tests:
  name: BSL Tests
  runs-on: windows-latest
  steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Run BSL manifest
      run: python scripts/tests/run_bsl_tests.py --manifest tests/bsl/testplan.json
    - name: Upload BSL test logs
      uses: actions/upload-artifact@v3
      with:
        name: bsl-test-artifacts
        path: output/bsl-tests
```

### Конфигурация testplan.json

```json
[
  {
    "name": "yaxunit-ai-generated-code",
    "command": [
      "python",
      "scripts/tests/run_yaxunit_tests.py",
      "--test-files",
      "test_ai_generated_code.bsl",
      "--report-format",
      "jUnit"
    ],
    "working_directory": ".",
    "env": {},
    "timeout": 1800
  }
]
```

## Генерация тестов через AI

### QA Agent Extended

QA Agent Extended автоматически генерирует YAxUnit тесты:

```python
from src.ai.agents.qa_engineer_agent_extended import QAEngineerAgentExtended

qa_agent = QAEngineerAgentExtended()

# Генерация тестов для AI-кода
test_code = await qa_agent.generate_yaxunit_tests_for_ai_code(
    generated_code="Функция Тест()...",
    function_name="Тест",
    test_scenarios=["normal_case", "edge_case", "error_case"],
)

# Сохранение тестов
test_file = Path("tests/bsl/test_ai_test.bsl")
test_file.write_text(test_code, encoding="utf-8")
```

## Отчеты и метрики

### Форматы отчетов

YAxUnit поддерживает несколько форматов отчетов:

- **jUnit XML** - для CI/CD интеграции
- **JSON** - для программной обработки
- **Allure** - для визуализации

### Просмотр отчетов

```bash
# JUnit отчет
cat output/bsl-tests/reports/report.xml

# Логи тестов
cat output/bsl-tests/logs/tests.log
```

### Метрики качества

```python
from src.services.ai_code_validator import AICodeValidator

validator = AICodeValidator()
result = await validator.validate_generated_code(...)

# Получение сводки
summary = validator.get_validation_summary(result)
print(f"Pass rate: {summary['pass_rate']:.1f}%")
print(f"Execution time: {summary['execution_time']:.2f}s")
```

## Troubleshooting

### Проблема: Тесты не запускаются

**Решение:**
1. Проверьте настройку информационной базы (`--ib-path` или `--ib-name`)
2. Убедитесь, что YAxUnit расширение загружено в ИБ
3. Проверьте права доступа к ИБ

### Проблема: Ошибка "1cv8c не найден"

**Решение:**
1. Укажите путь к 1cv8c через `--v8-path`
2. Или установите 1С:Предприятие в стандартное место

### Проблема: Тесты падают с ошибками

**Решение:**
1. Проверьте логи: `output/bsl-tests/logs/tests.log`
2. Убедитесь, что тестовые данные корректны
3. Проверьте, что все зависимости доступны в ИБ

## Best Practices

### 1. Структура тестов

- Используйте паттерн Arrange-Act-Assert
- Группируйте тесты по модулям
- Используйте описательные имена тестов

### 2. Генерация тестов

- Всегда генерируйте тесты для AI-кода
- Включайте edge cases и error cases
- Используйте property-based testing для сложных функций

### 3. CI/CD

- Запускайте тесты на каждом коммите
- Блокируйте merge при падении тестов
- Публикуйте отчеты в CI/CD

## Дополнительные ресурсы

- [Официальная документация YAxUnit](https://bia-technologies.github.io/yaxunit/)
- [Примеры тестов](../../tests/bsl/)
- [Анализ интеграции](../../analysis/YAXUNIT_INTEGRATION_ANALYSIS.md)
- [Глубокий анализ](../../analysis/yaxunit_usefulness_deep_analysis.md)

---

**Конец руководства**

