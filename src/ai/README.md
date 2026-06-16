# AI Core Modules

В каталоге собраны основные модули AI-платформы: агенты, MCP сервер, оркестратор, клиенты моделей и вспомогательные утилиты.

## Структура
| Каталог/файл | Назначение |
|--------------|------------|
| [`agents/`](agents/README.md) | Реализации AI-агентов (архитектор, разработчик, бизнес-аналитик и др.). |
| [`copilot/`](copilot/README.md) | Подготовка данных и обучение ML-компонент (dataset builder, fine-tuning). |
| [`mcp_server.py`](mcp_server.py), [`mcp_server_multi_role.py`](mcp_server_multi_role.py), [`mcp_server_architect.py`](mcp_server_architect.py) | MCP серверы для разных сценариев. |
| [`orchestrator.py`](orchestrator.py) | Координация взаимодействия агентов и сервисов. |
| [`role_based_router.py`](role_based_router.py) | Маршрутизация запросов между агентами. |
| [`qwen_client.py`](qwen_client.py) | Клиент к Qwen/LLM сервисам. |
| [`sql_optimizer_secure.py`](sql_optimizer_secure.py) | Безопасный SQL оптимизатор с проверками. |
| [`nl_to_cypher.py`](nl_to_cypher.py) | Преобразование natural language → Cypher запросы. |

## Связанные документы
- [docs/06-features/MCP_SERVER_GUIDE.md](../../docs/06-features/MCP_SERVER_GUIDE.md)
- [docs/06-features/AST_TOOLING_BSL_LANGUAGE_SERVER.md](../../docs/06-features/AST_TOOLING_BSL_LANGUAGE_SERVER.md)
- [docs/research/ba_agent_roadmap.md](../../docs/research/ba_agent_roadmap.md)
- [docs/research/bsl_language_server_plan.md](../../docs/research/bsl_language_server_plan.md)
