# 📦 EDT-Parser для конфигураций 1С

> **Полное руководство по парсингу конфигураций 1C:Enterprise Development Tools**

---

## 🎯 Что это такое?

**EDT-Parser** — это мощный инструмент для извлечения структурированных данных из конфигураций 1С:Enterprise, разработанных в Eclipse Development Tools (EDT).

### Возможности:

- 🔍 **Парсинг метаданных** - извлечение всех объектов конфигурации
- 📊 **Анализ кода** - извлечение функций, процедур, параметров
- 🔗 **Граф зависимостей** - связи между модулями и объектами
- 📈 **Статистика** - метрики сложности, размера, качества
- 💾 **Экспорт данных** - JSON, PostgreSQL, Neo4j, Qdrant

### Статистика проекта:

```
Обработано объектов:     6,708
Извлечено функций:       117,349
Успешность парсинга:     99.93%
Среднее время:           ~30 сек на 1000 объектов
```

---

## 🚀 Quick Start

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

**Требуется:**
- Python 3.10+
- lxml (для XML парсинга)
- pathlib (для работы с файлами)

### 2. Подготовка данных

EDT конфигурации хранятся в XML формате:

```
/path/to/configuration/
├── Configuration.xml         # Корневой файл конфигурации
├── Catalogs/                 # Справочники
│   ├── Catalog1/
│   │   ├── Catalog1.mdo
│   │   └── Forms/
│   └── Catalog2/
├── Documents/                # Документы
├── CommonModules/            # Общие модули
└── DataProcessors/           # Обработки
```

### 3. Базовый запуск

```bash
# Простой парсинг с выводом в JSON
python scripts/parsers/edt/edt_parser.py \
    --source /path/to/configuration \
    --output output/edt_parser/result.json
```

### 4. Расширенный парсинг с метаданными

```bash
# Парсинг с извлечением метаданных и статистики
python scripts/parsers/edt/edt_parser_with_metadata.py \
    --source /path/to/configuration \
    --output output/edt_parser/ \
    --include-code \
    --extract-dependencies
```

---

## 📖 Использование

### Базовый парсинг

```python
from scripts.parsers.edt.edt_parser import EDTParser

# Создание парсера
parser = EDTParser(
    source_path="/path/to/configuration",
    output_path="output/edt_parser/"
)

# Запуск парсинга
result = parser.parse()

print(f"Обработано объектов: {result['total_objects']}")
print(f"Извлечено функций: {result['total_functions']}")
```

### Парсинг с метаданными

```python
from scripts.parsers.edt.edt_parser_with_metadata import EDTParserWithMetadata

# Создание парсера с расширенными возможностями
parser = EDTParserWithMetadata(
    source_path="/path/to/configuration",
    output_path="output/edt_parser/",
    options={
        'include_code': True,           # Включить код функций
        'extract_dependencies': True,   # Извлечь зависимости
        'calculate_metrics': True,      # Рассчитать метрики
        'generate_graph': True          # Создать граф зависимостей
    }
)

# Запуск
result = parser.parse_all()
```

### Фильтрация объектов

```python
# Парсинг только справочников
result = parser.parse(
    object_types=['Catalog']
)

# Парсинг справочников и документов
result = parser.parse(
    object_types=['Catalog', 'Document']
)

# Парсинг с фильтром по имени
result = parser.parse(
    name_pattern='Номенклатура*'
)
```

---

## 📊 Формат выходных данных

### Структура JSON

```json
{
  "metadata": {
    "configuration_name": "УправлениеПредприятием",
    "version": "3.0.1",
    "parsed_at": "2025-11-06T23:59:59",
    "total_objects": 6708,
    "total_functions": 117349,
    "success_rate": 99.93
  },
  "objects": [
    {
      "type": "Catalog",
      "name": "Номенклатура",
      "uuid": "12345678-1234-1234-1234-123456789abc",
      "path": "Catalogs/Номенклатура/Номенклатура.mdo",
      "modules": [
        {
          "type": "ObjectModule",
          "path": "Catalogs/Номенклатура/ObjectModule.bsl",
          "functions": [
            {
              "name": "ПриЗаписи",
              "type": "procedure",
              "parameters": ["Отказ"],
              "line_start": 10,
              "line_end": 45,
              "code": "Процедура ПриЗаписи(Отказ)...",
              "complexity": 8,
              "api_calls": ["Запрос.", "Справочники."],
              "dependencies": ["ОбщиеМодули.РаботаСНоменклатурой"]
            }
          ],
          "metrics": {
            "total_lines": 450,
            "code_lines": 380,
            "comment_lines": 70,
            "cyclomatic_complexity": 45
          }
        }
      ],
      "forms": ["ФормаЭлемента", "ФормаСписка"],
      "attributes": [
        {"name": "Наименование", "type": "String", "length": 150},
        {"name": "Артикул", "type": "String", "length": 50}
      ]
    }
  ],
  "dependencies": {
    "Справочники.Номенклатура": [
      "ОбщиеМодули.РаботаСНоменклатурой",
      "Справочники.ЕдиницыИзмерения"
    ]
  },
  "statistics": {
    "by_type": {
      "Catalog": 1344,
      "Document": 847,
      "CommonModule": 156,
      "DataProcessor": 234,
      "Report": 189
    },
    "total_lines_of_code": 2450000,
    "average_function_complexity": 5.8
  }
}
```

---

## 🔧 Опции парсера

### Командная строка

```bash
python scripts/parsers/edt/edt_parser.py \
    --source PATH              # Путь к конфигурации (обязательно)
    --output PATH              # Путь для сохранения результатов
    --types TYPES              # Типы объектов (Catalog,Document,...)
    --include-code             # Включить код функций в результат
    --extract-dependencies     # Извлечь зависимости между объектами
    --calculate-metrics        # Рассчитать метрики сложности
    --generate-graph           # Создать граф зависимостей
    --parallel                 # Использовать многопоточность
    --threads N                # Количество потоков (по умолчанию: CPU count)
    --verbose                  # Подробный вывод
```

### Python API

```python
parser = EDTParserWithMetadata(
    source_path="/path/to/configuration",
    output_path="output/edt_parser/",
    options={
        # Что извлекать
        'include_code': True,              # Код функций
        'include_comments': True,          # Комментарии
        'include_forms': True,             # Формы
        'include_attributes': True,        # Реквизиты
        
        # Анализ
        'extract_dependencies': True,      # Зависимости
        'calculate_metrics': True,         # Метрики
        'detect_patterns': True,           # Паттерны кода
        'analyze_api_usage': True,         # Использование API
        
        # Оптимизация
        'use_cache': True,                 # Кэширование
        'parallel': True,                  # Многопоточность
        'threads': 8,                      # Количество потоков
        
        # Фильтры
        'object_types': ['Catalog', 'Document'],
        'name_pattern': 'Номенклатура*',
        'exclude_patterns': ['Test*', '*Demo'],
        
        # Вывод
        'verbose': True,                   # Подробный лог
        'progress_bar': True               # Прогресс-бар
    }
)
```

---

## 🔗 Интеграция с базами данных

### PostgreSQL

```python
from scripts.parsers.edt.edt_parser_with_metadata import EDTParserWithMetadata
from scripts.migrations.migrate_json_to_postgres import migrate_to_postgres

# 1. Парсинг
parser = EDTParserWithMetadata(source_path="/path/to/config")
result = parser.parse_all()

# 2. Сохранение в JSON
parser.save_json("output/edt_parser/result.json")

# 3. Миграция в PostgreSQL
migrate_to_postgres(
    json_path="output/edt_parser/result.json",
    db_url="postgresql://user:pass@localhost/knowledge_base"
)
```

### Neo4j (граф зависимостей)

```python
from scripts.migrations.migrate_postgres_to_neo4j import migrate_to_neo4j

# Миграция в Neo4j для построения графа
migrate_to_neo4j(
    pg_url="postgresql://user:pass@localhost/knowledge_base",
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)
```

### Qdrant (векторный поиск)

```python
from scripts.migrations.migrate_to_qdrant import migrate_to_qdrant

# Миграция в Qdrant для семантического поиска
migrate_to_qdrant(
    json_path="output/edt_parser/result.json",
    qdrant_host="localhost",
    qdrant_port=6333
)
```

---

## 📈 Оркестрация анализа

Для комплексного анализа используйте оркестратор:

```bash
# Полный цикл: парсинг → анализ → граф → отчет
bash scripts/orchestrate_edt_analysis.sh /path/to/configuration
```

**Что делает оркестратор:**

1. ✅ Парсинг конфигурации EDT
2. ✅ Извлечение метаданных и кода
3. ✅ Анализ архитектуры
4. ✅ Построение графа зависимостей
5. ✅ Выявление best practices
6. ✅ Генерация отчетов
7. ✅ Сохранение в БД (PostgreSQL, Neo4j, Qdrant)

**Результаты:**

```
output/edt_parser/
├── full_parse_with_metadata.json    # Полные данные
├── architecture_analysis.json       # Анализ архитектуры
├── dependency_graph.json            # Граф зависимостей
├── best_practices_report.json       # Отчет о качестве
└── parsing_log.txt                  # Лог парсинга
```

---

## 🎨 Визуализация в EDT Plugin

После парсинга данные доступны в EDT плагине:

### 1. Analysis Dashboard

```
Window → Show View → Other... → 1C AI Assistant → Analysis Dashboard
```

**Показывает:**
- Архитектурная статистика (модули, справочники, документы)
- Граф зависимостей
- Best Practices Score (качество кода)
- Тренды изменений

### 2. Metadata Graph View

```
Window → Show View → Other... → 1C AI Assistant → Metadata Graph
```

**Показывает:**
- Визуализация связей между объектами
- Интерактивный граф из Neo4j
- Поиск циклических зависимостей

### 3. Semantic Search

```
Window → Show View → Other... → 1C AI Assistant → Semantic Search
```

**Позволяет:**
- Искать код по смыслу (не по тексту)
- Находить похожие функции
- Использует векторный поиск Qdrant

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
python scripts/parsers/edt/test_edt_parser.py

# Комплексный тест
python scripts/parsers/edt/comprehensive_test.py
```

### Ручное тестирование

```python
from scripts.parsers.edt.edt_parser import EDTParser

# Тест на небольшой конфигурации
parser = EDTParser(
    source_path="test_data/simple_configuration",
    output_path="test_output/"
)

result = parser.parse()
assert result['success_rate'] > 95.0
print("✓ Тест пройден")
```

---

## 🐛 Troubleshooting

### Проблема: Парсер не находит конфигурацию

**Симптом:**
```
Error: Configuration.xml not found
```

**Решение:**
1. Убедитесь что путь указывает на корень конфигурации EDT
2. Проверьте наличие файла `Configuration.xml`
3. Используйте абсолютный путь

```bash
# Правильно
python edt_parser.py --source /full/path/to/configuration

# Неправильно
python edt_parser.py --source relative/path
```

---

### Проблема: Низкая успешность парсинга (<90%)

**Симптом:**
```
Success rate: 75.3% (expected >90%)
```

**Возможные причины:**
1. Конфигурация повреждена
2. Нестандартный формат XML
3. Неполная конфигурация (выгрузка без исходников)

**Решение:**
```bash
# Проверьте лог ошибок
cat output/edt_parser/parsing_log.txt | grep ERROR

# Запустите в verbose режиме
python edt_parser.py --source /path --verbose
```

---

### Проблема: Out of Memory при больших конфигурациях

**Симптом:**
```
MemoryError: Unable to allocate array
```

**Решение:**

1. **Увеличьте память Python:**
```bash
# Linux/Mac
export PYTHONMAXMEMORY=8G
python edt_parser.py --source /path

# Windows
set PYTHONMAXMEMORY=8G
python edt_parser.py --source /path
```

2. **Используйте потоковый парсинг:**
```python
parser = EDTParser(
    source_path="/path",
    options={
        'streaming_mode': True,    # Потоковая обработка
        'batch_size': 100          # По 100 объектов
    }
)
```

3. **Парсите по частям:**
```bash
# Только справочники
python edt_parser.py --source /path --types Catalog

# Только документы
python edt_parser.py --source /path --types Document
```

---

### Проблема: Медленный парсинг

**Симптом:**
```
Parsing takes >10 minutes for 1000 objects
```

**Решение:**

1. **Включите многопоточность:**
```bash
python edt_parser.py --source /path --parallel --threads 8
```

2. **Используйте кэширование:**
```python
parser = EDTParser(
    source_path="/path",
    options={'use_cache': True}
)
```

3. **Отключите ненужные опции:**
```python
parser = EDTParser(
    source_path="/path",
    options={
        'include_code': False,          # Не извлекать код
        'calculate_metrics': False,     # Не считать метрики
        'generate_graph': False         # Не строить граф
    }
)
```

---

### Проблема: Encoding errors в русских именах

**Симптом:**
```
UnicodeDecodeError: 'charmap' codec can't decode
```

**Решение:**
```python
# Явно указывайте UTF-8
parser = EDTParser(
    source_path="/path",
    options={'encoding': 'utf-8'}
)
```

```bash
# В командной строке
set PYTHONIOENCODING=utf-8  # Windows
export PYTHONIOENCODING=utf-8  # Linux/Mac

python edt_parser.py --source /path
```

---

## 📚 Примеры использования

### Пример 1: Анализ архитектуры конфигурации

```python
from scripts.parsers.edt.edt_parser_with_metadata import EDTParserWithMetadata

parser = EDTParserWithMetadata(
    source_path="/path/to/УправлениеПредприятием",
    output_path="output/analysis/"
)

result = parser.parse_all()

# Статистика по типам объектов
print("Объекты конфигурации:")
for obj_type, count in result['statistics']['by_type'].items():
    print(f"  {obj_type}: {count}")

# Самые сложные модули
complex_modules = sorted(
    result['objects'],
    key=lambda x: x.get('complexity', 0),
    reverse=True
)[:10]

print("\nТоп-10 самых сложных модулей:")
for module in complex_modules:
    print(f"  {module['name']}: complexity={module['complexity']}")
```

### Пример 2: Поиск неиспользуемых функций

```python
def find_unused_functions(parse_result):
    """Находит функции, которые нигде не вызываются"""
    
    all_functions = set()
    called_functions = set()
    
    for obj in parse_result['objects']:
        for module in obj.get('modules', []):
            for func in module.get('functions', []):
                func_name = f"{obj['name']}.{func['name']}"
                all_functions.add(func_name)
                
                # Анализируем вызовы
                for dep in func.get('dependencies', []):
                    called_functions.add(dep)
    
    unused = all_functions - called_functions
    return list(unused)

result = parser.parse_all()
unused = find_unused_functions(result)

print(f"Найдено неиспользуемых функций: {len(unused)}")
for func in unused[:20]:
    print(f"  {func}")
```

### Пример 3: Экспорт в CSV для Excel

```python
import csv

def export_to_csv(parse_result, output_file):
    """Экспорт в CSV для анализа в Excel"""
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Объект', 'Тип', 'Модуль', 'Функция', 'Сложность', 'Строк кода'])
        
        for obj in parse_result['objects']:
            for module in obj.get('modules', []):
                for func in module.get('functions', []):
                    writer.writerow([
                        obj['name'],
                        obj['type'],
                        module['type'],
                        func['name'],
                        func.get('complexity', 0),
                        func.get('line_end', 0) - func.get('line_start', 0)
                    ])

result = parser.parse_all()
export_to_csv(result, "analysis.csv")
print("✓ Экспорт завершен: analysis.csv")
```

---

## 🔗 Интеграция с CI/CD

### GitHub Actions

```yaml
name: EDT Configuration Analysis

on: [push]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Parse EDT configuration
        run: |
          python scripts/parsers/edt/edt_parser_with_metadata.py \
            --source ./configuration \
            --output ./output/edt_parser \
            --verbose
      
      - name: Check code quality
        run: |
          python scripts/check_quality.py \
            --input ./output/edt_parser/full_parse_with_metadata.json \
            --min-success-rate 95
      
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: edt-analysis
          path: output/edt_parser/
```

---

## 📖 Связанные документы

- [ML Dataset Generator](ML_DATASET_GENERATOR_GUIDE.md) - создание dataset из результатов парсинга
- [EDT Plugin Guide](../05-development/edt-plugin/README.md) - использование в Eclipse EDT
- [Architecture Overview](../02-architecture/ARCHITECTURE_OVERVIEW.md) - архитектура системы
- [Technology Stack](../02-architecture/TECHNOLOGY_STACK.md) - технологии проекта

---

## 💡 Best Practices

1. **Всегда используйте version control** для конфигураций EDT
2. **Кэшируйте результаты** парсинга для больших конфигураций
3. **Анализируйте изменения** между версиями конфигурации
4. **Автоматизируйте** парсинг в CI/CD
5. **Мониторьте качество** кода через метрики сложности

---

## 📞 Поддержка

- 📖 [Основная документация](../01-getting-started/README.md)
- 🐛 [Issue Tracker](https://github.com/DmitrL-dev/1cai-public/issues)
- 💬 [Discussions](https://github.com/DmitrL-dev/1cai-public/discussions)

---

*Последнее обновление: 6 ноября 2025*

