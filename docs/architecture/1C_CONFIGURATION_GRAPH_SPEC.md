# 1C Configuration Graph Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - граф конфигурации 1C уникален

---

## Обзор

**1C Configuration Graph Standard** — формальная спецификация для построения графа конфигурации 1C. Определяет связи между объектами метаданных, зависимости между модулями и объектами, алгоритмы построения графа из метаданных и BSL кода.

---

## 1. Структура графа конфигурации

### 1.1 Типы узлов конфигурации

```python
CONFIGURATION_NODE_KINDS = {
    # Объекты метаданных
    "bsl_document": "Документ",
    "bsl_catalog": "Справочник",
    "bsl_common_module": "Общий модуль",
    "bsl_register_information": "Регистр сведений",
    "bsl_register_accumulation": "Регистр накопления",
    "bsl_register_accounting": "Регистр бухгалтерии",
    "bsl_report": "Отчет",
    "bsl_data_processor": "Обработка",
    
    # Модули объектов
    "bsl_object_module": "Модуль объекта",
    "bsl_manager_module": "Модуль менеджера",
    "bsl_form_module": "Модуль формы",
    "bsl_command_module": "Модуль команды",
    
    # Формы и команды
    "bsl_form": "Форма объекта",
    "bsl_command": "Команда объекта",
    
    # Другие узлы
    "bsl_query": "SQL-запрос",
    "function": "Функция",
    "procedure": "Процедура",
}
```

### 1.2 Типы связей конфигурации

```python
CONFIGURATION_EDGE_KINDS = {
    # Структура объектов
    "BSL_HAS_MODULE": "Объект имеет модуль",
    "BSL_HAS_FORM": "Объект имеет форму",
    "BSL_HAS_COMMAND": "Объект имеет команду",
    
    # Зависимости между объектами
    "BSL_REFERENCES": "Объект ссылается на другой объект",
    "BSL_EXTENDS": "Объект расширяет другой объект",
    "BSL_SUBTYPE": "Объект является подтипом другого объекта",
    "BSL_HAS_REGISTER": "Документ/обработка имеет регистр",
    
    # Зависимости в коде
    "BSL_CALLS": "Вызов функции/процедуры",
    "BSL_USES_METADATA": "Использование объекта метаданных в коде",
    "BSL_EXECUTES_QUERY": "Выполнение SQL-запроса",
    "BSL_READS_TABLE": "Чтение таблицы БД",
    "BSL_WRITES_TABLE": "Запись в таблицу БД",
    
    # Структура модулей
    "OWNS": "Модуль содержит функцию/процедуру",
    "DEPENDS_ON": "Зависимость между модулями",
}
```

---

## 2. Алгоритмы построения графа

### 2.1 Построение из метаданных XML

```python
async def build_configuration_graph_from_xml(
    xml_file: Path,
    backend: CodeGraphBackend,
) -> Dict[str, int]:
    """
    Построение графа конфигурации из XML метаданных.
    
    Args:
        xml_file: Путь к XML файлу конфигурации
        backend: Backend графа
    
    Returns:
        Статистика построения
    """
    # 1. Парсинг XML метаданных
    metadata = await extract_metadata_from_xml(xml_file)
    
    # 2. Создание узлов объектов метаданных
    stats = await create_metadata_nodes_in_graph(metadata, backend)
    
    # 3. Создание связей между объектами
    stats["edges_created"] += await create_metadata_relationships(metadata, backend)
    
    return stats
```

### 2.2 Построение из BSL кода

```python
async def build_configuration_graph_from_bsl(
    bsl_files: List[Path],
    backend: CodeGraphBackend,
) -> Dict[str, int]:
    """
    Построение графа конфигурации из BSL кода.
    
    Args:
        bsl_files: Список путей к BSL файлам
        backend: Backend графа
    
    Returns:
        Статистика построения
    """
    from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder
    
    builder = OneCCodeGraphBuilder(backend)
    
    total_stats = {
        "nodes_created": 0,
        "edges_created": 0,
    }
    
    for bsl_file in bsl_files:
        module_code = bsl_file.read_text(encoding="utf-8")
        module_path = determine_module_path(bsl_file)
        
        stats = await builder.build_from_module(
            module_path,
            module_code,
            module_metadata={"file_path": str(bsl_file)},
        )
        
        total_stats["nodes_created"] += stats["nodes_created"]
        total_stats["edges_created"] += stats["edges_created"]
    
    return total_stats
```

### 2.3 Объединение графов

```python
async def merge_configuration_graphs(
    metadata_graph: CodeGraphBackend,
    bsl_graph: CodeGraphBackend,
    target_backend: CodeGraphBackend,
) -> Dict[str, int]:
    """
    Объединение графов метаданных и BSL кода.
    
    Args:
        metadata_graph: Граф из метаданных
        bsl_graph: Граф из BSL кода
        target_backend: Целевой backend для объединенного графа
    
    Returns:
        Статистика объединения
    """
    stats = {
        "nodes_merged": 0,
        "edges_merged": 0,
    }
    
    # Объединение узлов объектов метаданных
    metadata_nodes = await metadata_graph.find_nodes(
        kind=NodeKind.BSL_DOCUMENT,  # и другие типы
    )
    
    for node in metadata_nodes:
        # Проверяем, существует ли узел в BSL графе
        bsl_module = await bsl_graph.find_nodes(
            prop_equals={"metadata_path": node.props.get("metadata_path")},
        )
        
        if bsl_module:
            # Объединяем свойства узлов
            merged_node = merge_node_properties(node, bsl_module[0])
        else:
            merged_node = node
        
        await target_backend.upsert_node(merged_node)
        stats["nodes_merged"] += 1
    
    # Объединение связей
    # ...
    
    return stats
```

---

## 3. Связи между объектами метаданных

### 3.1 Ссылки на другие объекты

```python
async def create_metadata_references(
    metadata: Dict[str, Any],
    backend: CodeGraphBackend,
) -> int:
    """
    Создание связей BSL_REFERENCES между объектами метаданных.
    
    Returns:
        Количество созданных связей
    """
    edges_created = 0
    
    for obj_type, objects in metadata.items():
        for obj in objects:
            obj_node_id = f"{METADATA_OBJECT_TYPES[obj_type]}:{obj['metadata_path']}"
            
            # Извлечение ссылок из свойств объекта
            references = extract_references_from_object(obj)
            
            for ref_metadata_path in references:
                ref_node = await backend.find_nodes(
                    prop_equals={"metadata_path": ref_metadata_path},
                )
                
                if ref_node:
                    edge = Edge(
                        source=obj_node_id,
                        target=ref_node[0].id,
                        kind=EdgeKind.BSL_REFERENCES,
                    )
                    await backend.upsert_edge(edge)
                    edges_created += 1
    
    return edges_created
```

### 3.2 Наследование объектов

```python
async def create_metadata_inheritance(
    metadata: Dict[str, Any],
    backend: CodeGraphBackend,
) -> int:
    """
    Создание связей BSL_EXTENDS для наследования объектов.
    
    Returns:
        Количество созданных связей
    """
    edges_created = 0
    
    for obj_type, objects in metadata.items():
        for obj in objects:
            # Проверка наличия родительского объекта
            parent_path = obj.get("properties", {}).get("parent", None)
            if not parent_path:
                continue
            
            obj_node_id = f"{METADATA_OBJECT_TYPES[obj_type]}:{obj['metadata_path']}"
            
            parent_node = await backend.find_nodes(
                prop_equals={"metadata_path": parent_path},
            )
            
            if parent_node:
                edge = Edge(
                    source=obj_node_id,
                    target=parent_node[0].id,
                    kind=EdgeKind.BSL_EXTENDS,
                )
                await backend.upsert_edge(edge)
                edges_created += 1
    
    return edges_created
```

### 3.3 Связь с регистрами

```python
async def create_register_relationships(
    metadata: Dict[str, Any],
    backend: CodeGraphBackend,
) -> int:
    """
    Создание связей BSL_HAS_REGISTER для документов/обработок с регистрами.
    
    Returns:
        Количество созданных связей
    """
    edges_created = 0
    
    # Найти все документы и обработки
    documents = metadata.get("documents", [])
    data_processors = metadata.get("data_processors", [])
    
    all_objects = documents + data_processors
    
    for obj in all_objects:
        obj_node_id = f"{METADATA_OBJECT_TYPES[obj['type']]}:{obj['metadata_path']}"
        
        # Извлечение регистров из свойств объекта
        registers = extract_registers_from_object(obj)
        
        for register_path in registers:
            register_node = await backend.find_nodes(
                prop_equals={"metadata_path": register_path},
            )
            
            if register_node:
                edge = Edge(
                    source=obj_node_id,
                    target=register_node[0].id,
                    kind=EdgeKind.BSL_HAS_REGISTER,
                )
                await backend.upsert_edge(edge)
                edges_created += 1
    
    return edges_created
```

---

## 4. Зависимости между модулями и объектами

### 4.1 Построение зависимостей модулей

```python
async def build_module_dependencies(
    backend: CodeGraphBackend,
) -> int:
    """
    Построение зависимостей между модулями на основе вызовов функций.
    
    Returns:
        Количество созданных связей
    """
    edges_created = 0
    
    # Найти все модули
    modules = await backend.find_nodes(kind=NodeKind.BSL_OBJECT_MODULE)
    modules.extend(await backend.find_nodes(kind=NodeKind.BSL_MANAGER_MODULE))
    modules.extend(await backend.find_nodes(kind=NodeKind.BSL_FORM_MODULE))
    modules.extend(await backend.find_nodes(kind=NodeKind.MODULE))
    
    for module in modules:
        # Найти все функции в модуле
        functions = await backend.neighbors(
            module.id,
            kinds=[EdgeKind.OWNS],
        )
        
        # Для каждой функции найти вызываемые функции
        for func in functions:
            called_functions = await backend.neighbors(
                func.id,
                kinds=[EdgeKind.BSL_CALLS],
            )
            
            # Определить модули вызываемых функций
            for called_func in called_functions:
                called_module = await find_module_for_function(called_func, backend)
                
                if called_module and called_module.id != module.id:
                    # Создать связь между модулями
                    edge = Edge(
                        source=module.id,
                        target=called_module.id,
                        kind=EdgeKind.DEPENDS_ON,
                        props={"via_function": func.id},
                    )
                    await backend.upsert_edge(edge)
                    edges_created += 1
    
    return edges_created
```

### 4.2 Построение зависимостей объектов

```python
async def build_object_dependencies(
    backend: CodeGraphBackend,
) -> int:
    """
    Построение зависимостей между объектами метаданных.
    
    Returns:
        Количество созданных связей
    """
    edges_created = 0
    
    # Найти все объекты метаданных
    metadata_kinds = [
        NodeKind.BSL_DOCUMENT,
        NodeKind.BSL_CATALOG,
        NodeKind.BSL_REGISTER_INFORMATION,
        NodeKind.BSL_REGISTER_ACCUMULATION,
        NodeKind.BSL_REGISTER_ACCOUNTING,
    ]
    
    for kind in metadata_kinds:
        objects = await backend.find_nodes(kind=kind)
        
        for obj in objects:
            # Найти модули объекта
            modules = await backend.neighbors(
                obj.id,
                kinds=[EdgeKind.BSL_HAS_MODULE],
            )
            
            # Для каждого модуля найти использование метаданных
            for module in modules:
                metadata_usage = await backend.neighbors(
                    module.id,
                    kinds=[EdgeKind.BSL_USES_METADATA],
                )
                
                # Создать связи между объектами
                for used_obj in metadata_usage:
                    if used_obj.id != obj.id:
                        edge = Edge(
                            source=obj.id,
                            target=used_obj.id,
                            kind=EdgeKind.BSL_USES_METADATA,
                        )
                        await backend.upsert_edge(edge)
                        edges_created += 1
    
    return edges_created
```

---

## 5. JSON Schema для графа конфигурации

См. `BSL_CODE_GRAPH_SCHEMA.json` — используется та же схема с расширенными типами узлов и связей для конфигурации.

---

## 6. Примеры использования

### 6.1 Построение полного графа конфигурации

```python
from src.ai.code_graph import InMemoryCodeGraphBackend
from src.ai.configuration_graph import ConfigurationGraphBuilder

backend = InMemoryCodeGraphBackend()
builder = ConfigurationGraphBuilder(backend)

# Построение из XML
stats_xml = await builder.build_from_xml("config.xml")

# Построение из BSL
stats_bsl = await builder.build_from_bsl(["module1.bsl", "module2.bsl"])

# Объединение графов
stats_merged = await builder.merge_graphs()

print(f"Всего узлов: {stats_merged['nodes_created']}")
print(f"Всего связей: {stats_merged['edges_created']}")
```

### 6.2 Анализ зависимостей

```python
from src.ai.code_graph_query_helper import GraphQueryHelper

helper = GraphQueryHelper(backend)

# Найти все зависимости документа
document_node = await helper.find_nodes(
    prop_equals={"metadata_path": "Документы.ЗаказыПокупателей"},
)

if document_node:
    dependencies = await helper.neighbors(
        document_node[0].id,
        kinds=[EdgeKind.DEPENDS_ON, EdgeKind.BSL_USES_METADATA],
    )
    
    print(f"Зависимости: {[n.display_name for n in dependencies]}")
```

---

## 7. Следующие шаги

1. **Реализация построителя графа** — создание `ConfigurationGraphBuilder`
2. **Интеграция с метаданными** — автоматическое построение графа из XML
3. **Визуализация графа** — создание инструментов для визуализации графа конфигурации

---

**Примечание:** Этот стандарт обеспечивает автоматическое построение графа конфигурации 1C и анализ зависимостей между объектами.

