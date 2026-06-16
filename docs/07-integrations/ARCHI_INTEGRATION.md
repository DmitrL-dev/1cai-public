# Archi Integration — Руководство

**Версия:** 1.0 | **Статус:** ✅ Available

## Обзор

**Archi** — open-source инструмент для создания архитектурных диаграмм (ArchiMate). Интеграция с 1C AI Stack позволяет автоматически генерировать архитектурные диаграммы из кода 1C.

**Возможности:**
- 🏗️ Автоматическая генерация ArchiMate диаграмм
- 📊 Экспорт архитектуры 1C в Archi format
- 🔄 Синхронизация кода ↔ архитектуры
- 📈 Визуализация зависимостей

## Quick Start

```bash
# 1. Установка Archi
# Download from https://www.archimatetool.com/download/

# 2. Установка 1C AI Stack plugin для Archi
cd plugins/archi
./install.sh

# 3. Генерация диаграммы из кода
python scripts/generate_archi_diagram.py \
  --source /path/to/1c/project \
  --output architecture.archimate
```

## Configuration

```yaml
# archi_config.yml
export:
  format: archimate_3.1
  include:
    - modules
    - dependencies
    - data_flows
  exclude:
    - tests
    - temp_files

visualization:
  layout: hierarchical
  show_labels: true
  color_scheme: default
```

## Features

### 1. Code to Architecture

```python
from archi_integration import CodeToArchi

# Анализ кода и генерация диаграммы
converter = CodeToArchi(
    source_path="/path/to/1c/project",
    output_format="archimate"
)

diagram = converter.generate()
diagram.save("architecture.archimate")
```

### 2. Dependency Visualization

```python
# Визуализация зависимостей между модулями
from archi_integration import DependencyVisualizer

visualizer = DependencyVisualizer()
diagram = visualizer.create_dependency_diagram(
    modules=["sales", "inventory", "accounting"]
)
```

### 3. Export to Archi

```python
# Экспорт в Archi format
from archi_integration import ArchiExporter

exporter = ArchiExporter()
exporter.export(
    source="1c_architecture.json",
    output="architecture.archimate",
    format="archimate_3.1"
)
```

## API Integration

```python
# Использование через API
import requests

response = requests.post(
    "http://localhost:8000/api/v1/archi/generate",
    json={
        "source_path": "/path/to/1c/project",
        "output_format": "archimate",
        "include_dependencies": True
    }
)

archimate_xml = response.json()["diagram"]
```

## Diagram Types

### 1. Application Architecture

```python
# Генерация application architecture diagram
diagram = converter.generate_application_architecture(
    layers=["presentation", "business", "data"],
    show_interfaces=True
)
```

### 2. Technology Architecture

```python
# Генерация technology architecture diagram
diagram = converter.generate_technology_architecture(
    components=["database", "app_server", "web_server"],
    show_connections=True
)
```

### 3. Data Flow Diagram

```python
# Генерация data flow diagram
diagram = converter.generate_data_flow(
    processes=["order_processing", "inventory_update"],
    show_data_stores=True
)
```

## Examples

### Example 1: Generate Full Architecture

```bash
# Полная архитектура проекта
python scripts/generate_archi_diagram.py \
  --source /path/to/1c/project \
  --type full \
  --output full_architecture.archimate
```

### Example 2: Module Dependencies

```python
# Зависимости конкретного модуля
from archi_integration import ModuleDependencies

deps = ModuleDependencies("sales_module")
diagram = deps.generate_diagram()
diagram.save("sales_dependencies.archimate")
```

## Integration with Archi Tool

```bash
# 1. Открыть Archi
# 2. File → Import → ArchiMate Model
# 3. Выбрать generated .archimate file
# 4. Customize layout and styling
# 5. Export to PNG/SVG for documentation
```

## Troubleshooting

**Проблема:** Diagram generation fails  
**Решение:** Проверьте что source path содержит valid 1C project

**Проблема:** Invalid ArchiMate format  
**Решение:** Обновите plugin до latest version

## FAQ

**Q: Какая версия Archi поддерживается?**  
A: Archi >= 4.9.0

**Q: Можно ли кастомизировать диаграммы?**  
A: Да, через archi_config.yml

**Q: Поддерживается ли ArchiMate 3.1?**  
A: Да, полная поддержка

---

**См. также:**
- [Archi Documentation](https://www.archimatetool.com/documentation/)
- [Architecture Overview](../02-architecture/ARCHITECTURE_OVERVIEW.md)
