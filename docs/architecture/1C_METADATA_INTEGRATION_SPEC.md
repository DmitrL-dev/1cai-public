# 1C Metadata Integration Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - специфика 1C метаданных

---

## Обзор

**1C Metadata Integration Standard** — формальная спецификация для интеграции с метаданными конфигурации 1C:Предприятие. Определяет стандарты работы с Документами, Регистрами, Справочниками, алгоритмы извлечения метаданных из .xml файлов и интеграцию с BSL Code Graph.

---

## 1. Типы объектов метаданных 1C

### 1.1 Основные объекты

```python
METADATA_OBJECT_TYPES = {
    # Основные объекты
    'Документ': 'bsl_document',
    'Справочник': 'bsl_catalog',
    'ОбщийМодуль': 'bsl_common_module',
    
    # Регистры
    'РегистрСведений': 'bsl_register_information',
    'РегистрНакопления': 'bsl_register_accumulation',
    'РегистрБухгалтерии': 'bsl_register_accounting',
    
    # Отчеты и обработки
    'Отчет': 'bsl_report',
    'Обработка': 'bsl_data_processor',
    
    # Планы
    'ПланСчетов': 'bsl_chart_of_accounts',
    'ПланВидовХарактеристик': 'bsl_chart_of_characteristic_types',
    'ПланВидовРасчета': 'bsl_chart_of_calculation_types',
    
    # Процессы и задачи
    'БизнесПроцесс': 'bsl_business_process',
    'Задача': 'bsl_task',
    
    # Прочие
    'Константа': 'bsl_constant',
    'Перечисление': 'bsl_enum',
    'ВнешняяОбработка': 'bsl_external_data_processor',
    'ВнешнийОтчет': 'bsl_external_report',
    'HTTPСервис': 'bsl_http_service',
    'WSСсылка': 'bsl_ws_reference',
    'ПланОбмена': 'bsl_exchange_plan',
}
```

### 1.2 Типы модулей в объектах

```python
MODULE_TYPES = {
    'ObjectModule': 'bsl_object_module',        # Модуль объекта
    'ManagerModule': 'bsl_manager_module',      # Модуль менеджера
    'FormModule': 'bsl_form_module',            # Модуль формы
    'CommandModule': 'bsl_command_module',      # Модуль команды
    'RecordSetModule': 'bsl_record_set_module', # Модуль набора записей
}
```

---

## 2. Извлечение метаданных из XML

### 2.1 Структура XML конфигурации

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.1/data/core">
    <Configuration>
        <Documents>
            <Document name="ЗаказыПокупателей">
                <uuid>12345678-1234-1234-1234-123456789012</uuid>
                <Properties>
                    <NumberPeriodicity>Year</NumberPeriodicity>
                    <CheckUnique>true</CheckUnique>
                </Properties>
                <ObjectModule>
                    <Name>Объект</Name>
                    <Content>...</Content>
                </ObjectModule>
                <ManagerModule>
                    <Name>Менеджер</Name>
                    <Content>...</Content>
                </ManagerModule>
            </Document>
        </Documents>
    </Configuration>
</MetaDataObject>
```

### 2.2 Алгоритм извлечения

```python
async def extract_metadata_from_xml(xml_file: Path) -> Dict[str, Any]:
    """
    Извлечение метаданных из XML файла конфигурации.
    
    Args:
        xml_file: Путь к XML файлу конфигурации
    
    Returns:
        Словарь с метаданными всех объектов
    """
    import xml.etree.ElementTree as ET
    
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    metadata = {
        "documents": [],
        "catalogs": [],
        "registers": [],
        "reports": [],
        "data_processors": [],
        "common_modules": [],
    }
    
    # Определение namespace
    namespace = detect_namespace(root)
    
    # Извлечение объектов метаданных
    for obj_type, node_kind in METADATA_OBJECT_TYPES.items():
        objects = root.findall(f'.//{{{namespace}}}{obj_type}')
        for obj in objects:
            obj_metadata = extract_object_metadata(obj, obj_type, namespace)
            metadata[obj_type.lower() + 's'].append(obj_metadata)
    
    return metadata
```

### 2.3 Извлечение метаданных объекта

```python
def extract_object_metadata(
    obj: ET.Element,
    obj_type: str,
    namespace: str,
) -> Dict[str, Any]:
    """
    Извлечение метаданных одного объекта.
    
    Returns:
        {
            "name": str,                    # Имя объекта
            "uuid": str,                    # UUID объекта
            "type": str,                    # Тип объекта
            "metadata_path": str,           # Путь к объекту (например, "Документы.ЗаказыПокупателей")
            "modules": List[Dict],          # Список модулей объекта
            "forms": List[Dict],            # Список форм объекта
            "commands": List[Dict],         # Список команд объекта
            "properties": Dict,             # Свойства объекта
        }
    """
    name = obj.get('name', '') or obj.get('Имя', '')
    uuid = obj.find(f'.//{{{namespace}}}uuid')
    uuid_value = uuid.text if uuid is not None else None
    
    # Определение пути к объекту
    if obj_type == 'Документ':
        metadata_path = f"Документы.{name}"
    elif obj_type == 'Справочник':
        metadata_path = f"Справочники.{name}"
    elif obj_type == 'РегистрСведений':
        metadata_path = f"РегистрыСведений.{name}"
    # ... и т.д.
    
    # Извлечение модулей
    modules = []
    for module_type in MODULE_TYPES:
        module = obj.find(f'.//{{{namespace}}}{module_type}')
        if module is not None:
            modules.append({
                "type": module_type,
                "name": module.find(f'.//{{{namespace}}}Name').text if module.find(f'.//{{{namespace}}}Name') is not None else None,
                "content": module.find(f'.//{{{namespace}}}Content').text if module.find(f'.//{{{namespace}}}Content') is not None else None,
            })
    
    return {
        "name": name,
        "uuid": uuid_value,
        "type": obj_type,
        "metadata_path": metadata_path,
        "modules": modules,
        "forms": extract_forms(obj, namespace),
        "commands": extract_commands(obj, namespace),
        "properties": extract_properties(obj, namespace),
    }
```

---

## 3. Интеграция с BSL Code Graph

### 3.1 Создание узлов метаданных в графе

```python
async def create_metadata_nodes_in_graph(
    metadata: Dict[str, Any],
    backend: CodeGraphBackend,
) -> Dict[str, int]:
    """
    Создание узлов метаданных в графе.
    
    Args:
        metadata: Метаданные конфигурации
        backend: Backend графа
    
    Returns:
        Статистика создания узлов
    """
    stats = {
        "nodes_created": 0,
        "edges_created": 0,
    }
    
    # Создание узлов для каждого типа объектов
    for obj_type, objects in metadata.items():
        if not objects:
            continue
        
        node_kind = METADATA_OBJECT_TYPES.get(obj_type.rstrip('s'), None)
        if not node_kind:
            continue
        
        for obj in objects:
            # Создание узла объекта метаданных
            node = Node(
                id=f"{node_kind}:{obj['metadata_path']}",
                kind=NodeKind(node_kind),
                display_name=f"{obj_type[:-1]}: {obj['name']}",
                labels=["bsl", "1c", "metadata", obj_type.rstrip('s')],
                props={
                    "metadata_path": obj["metadata_path"],
                    "uuid": obj.get("uuid"),
                    "name": obj["name"],
                    "type": obj["type"],
                },
            )
            await backend.upsert_node(node)
            stats["nodes_created"] += 1
            
            # Создание узлов модулей и связей
            for module in obj.get("modules", []):
                module_node = await create_module_node(
                    obj["metadata_path"],
                    module,
                    backend,
                )
                
                # Связь: объект имеет модуль
                edge = Edge(
                    source=node.id,
                    target=module_node.id,
                    kind=EdgeKind.BSL_HAS_MODULE,
                )
                await backend.upsert_edge(edge)
                stats["edges_created"] += 1
    
    return stats
```

---

## 4. Работа с объектами метаданных в коде

### 4.1 Извлечение использования метаданных из BSL кода

```python
def extract_metadata_usage(code: str) -> List[str]:
    """
    Извлечение использования объектов метаданных из BSL кода.
    
    Returns:
        Список путей к объектам метаданных
    """
    metadata_used = []
    
    # Паттерны для поиска использования метаданных
    patterns = [
        r'Метаданные\.Документы\.(\w+)',
        r'Метаданные\.Справочники\.(\w+)',
        r'Метаданные\.РегистрыСведений\.(\w+)',
        r'Документы\.(\w+)',
        r'Справочники\.(\w+)',
        r'РегистрыСведений\.(\w+)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, code)
        for match in matches:
            if 'Метаданные.' in match.group(0):
                metadata_path = match.group(0)
            else:
                # Определяем тип объекта по паттерну
                obj_name = match.group(1)
                if 'Документы' in pattern:
                    metadata_path = f"Документы.{obj_name}"
                elif 'Справочники' in pattern:
                    metadata_path = f"Справочники.{obj_name}"
                # ... и т.д.
            
            if metadata_path not in metadata_used:
                metadata_used.append(metadata_path)
    
    return metadata_used
```

---

## 5. JSON Schema для метаданных

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/1c-metadata/v1",
  "title": "1CMetadata",
  "type": "object",
  "required": ["name", "type", "metadata_path"],
  "properties": {
    "name": {"type": "string"},
    "uuid": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "type": {
      "type": "string",
      "enum": ["Документ", "Справочник", "РегистрСведений", "РегистрНакопления", "РегистрБухгалтерии", "Отчет", "Обработка", "ОбщийМодуль"]
    },
    "metadata_path": {"type": "string"},
    "modules": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {"type": "string"},
          "name": {"type": "string"},
          "content": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 6. Примеры использования

### 6.1 Извлечение метаданных

```python
from scripts.parsers.parse_1c_config_fixed import Fixed1CConfigParser

parser = Fixed1CConfigParser()
metadata = parser.extract_all_metadata(root, "ERP", config_file)

# metadata содержит все объекты метаданных
```

### 6.2 Интеграция с графом

```python
from src.ai.code_graph import InMemoryCodeGraphBackend
from src.ai.metadata_integration import create_metadata_nodes_in_graph

backend = InMemoryCodeGraphBackend()
stats = await create_metadata_nodes_in_graph(metadata, backend)

print(f"Создано узлов: {stats['nodes_created']}")
print(f"Создано связей: {stats['edges_created']}")
```

---

## 7. Следующие шаги

1. **Реализация парсера метаданных** — создание полного парсера для всех типов объектов
2. **Интеграция с графом** — автоматическое создание узлов метаданных в графе
3. **Валидация метаданных** — проверка корректности метаданных конфигурации

---

**Примечание:** Этот стандарт обеспечивает единообразную работу с метаданными 1C и их интеграцию с BSL Code Graph.

