# MCP Server 1C Extended Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 95% - MCP Server для 1C уникален

---

## Обзор

**MCP Server 1C Extended Standard** — формальная спецификация для расширенного MCP Server для 1C. Определяет интеграцию с Unified Change Graph через MCP, 1C специфичные MCP инструменты и интеграцию с AI агентами через MCP.

---

## 1. Интеграция с Unified Change Graph через MCP

### 1.1 MCP Tools для работы с графом

```python
MCP_TOOLS_FOR_GRAPH = [
    MCPTool(
        name="search_graph_nodes",
        description="Поиск узлов в Unified Change Graph по запросу",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "node_kind": {"type": "string"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    MCPTool(
        name="get_node_neighbors",
        description="Получение соседей узла в графе",
        input_schema={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "edge_kind": {"type": "string"},
            },
            "required": ["node_id"],
        },
    ),
    MCPTool(
        name="analyze_impact",
        description="Анализ влияния изменения узла",
        input_schema={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "max_depth": {"type": "integer", "default": 3},
            },
            "required": ["node_id"],
        },
    ),
]
```

---

## 2. 1C специфичные MCP инструменты

### 2.1 Инструменты для метаданных

```python
MCP_TOOLS_FOR_METADATA = [
    MCPTool(
        name="search_1c_metadata",
        description="Поиск объектов метаданных 1C",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "metadata_type": {
                    "type": "string",
                    "enum": ["document", "catalog", "register", "report"],
                },
                "configuration": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    MCPTool(
        name="get_metadata_modules",
        description="Получение модулей объекта метаданных",
        input_schema={
            "type": "object",
            "properties": {
                "metadata_path": {"type": "string"},
            },
            "required": ["metadata_path"],
        },
    ),
]
```

### 2.2 Инструменты для BSL кода

```python
MCP_TOOLS_FOR_BSL = [
    MCPTool(
        name="parse_bsl_code",
        description="Парсинг BSL кода через стандартный парсер",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "use_ast": {"type": "boolean", "default": True},
            },
            "required": ["code"],
        },
    ),
    MCPTool(
        name="build_bsl_graph",
        description="Построение BSL Code Graph из кода",
        input_schema={
            "type": "object",
            "properties": {
                "module_path": {"type": "string"},
                "module_code": {"type": "string"},
            },
            "required": ["module_path", "module_code"],
        },
    ),
]
```

---

## 3. Интеграция с AI агентами через MCP

```python
MCP_TOOLS_FOR_AI_AGENTS = [
    MCPTool(
        name="call_ai_agent",
        description="Вызов AI агента через MCP",
        input_schema={
            "type": "object",
            "properties": {
                "agent_role": {
                    "type": "string",
                    "enum": ["developer", "business_analyst", "qa_engineer"],
                },
                "query": {"type": "string"},
                "context": {"type": "object"},
            },
            "required": ["agent_role", "query"],
        },
    ),
]
```

---

## 4. JSON Schema для MCP интеграции

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/mcp-1c-integration/v1",
  "title": "MCP1CIntegrationMessage",
  "type": "object",
  "required": ["tool", "arguments"],
  "properties": {
    "tool": {"type": "string"},
    "arguments": {"type": "object"},
    "result": {"type": "object"}
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает полную интеграцию MCP Server с 1C специфичными инструментами и графом.

