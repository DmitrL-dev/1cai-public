# AI Modules — LEGACY (pre-Рентген), NOT on the product path

> **Status: legacy / quarantined (rc0 audit, 2026-06).** This tree (~21K LOC: agents,
> MCP servers, orchestrator, role router, GigaChat/YandexGPT/Qwen clients) predates
> **1С:Рентген** and is **not** invoked by the token-free Рентген flow. The product engine
> (`tools/rentgen/`) and analytics APIs (`rentgen_api`, `quality_api`) never call any LLM;
> the only "AI" in the product path is the token-free micro-perceptron `SwarmRouter`
> (`src/micro_swarm/`).
>
> Reachable only from legacy `src/modules/*` routers (assistants, ba_sessions,
> code_approval, github_integration, test_generation) and the orchestrator/council API
> routers — the latter **now unmounted** in `src/app/routers.py` to shrink attack surface.
> **Do not** wire this into the Рентген path — it would break the "token-free / code never
> leaves the host" guarantee. Full removal is a deliberate follow-up (it cascades into the
> legacy module routers that import it). See `docs/RENTGEN.md` ("Что факт, что эвристика").

Ниже — справка по содержимому каталога (сохранена как ориентир), но это **НЕ** продуктовый путь Рентгена.

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
