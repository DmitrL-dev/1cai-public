# Multi-Role Agents Evidence Contract

Дата: 2026-06-20.

## Зачем

Multi-role MCP и базовые BA/QA агенты отдавали демонстрационные фикстуры как `success`: вымышленные продажи, заказы, 65% покрытия, 45 модулей, 12 ошибок и заглушки документации. Для покупателя это разрушает доверие быстрее, чем отсутствие функции.

## Что сделано

- `BusinessAnalystAgent` переведен на локальное извлечение из переданного текста: требования, НФТ, user stories, acceptance criteria, summary, coverage и caveats.
- `QAEngineerAgent` больше не показывает ложные 65% покрытия и чужие функции; покрытие помечается как `unknown_no_test_evidence` с false-safe-zero caveat.
- Добавлены совместимые методы QA для `RoleBasedRouter`: `generate_tests`, `analyze_coverage`, `analyze_bugs`, `generate_performance_test`.
- `MultiRoleMCPServer` больше не возвращает выдуманные архитектурные, DevOps и documentation данные; вместо этого отдает `offline_mcp_contract` с required evidence.
- `src.ai.agents` теперь не падает в baseline из-за optional `SecurityAgent`/LLM зависимостей.

## Проверка

- `pytest tests\unit\test_multi_role_agents_evidence_contract.py tests\unit\test_role_based_router_contract.py tests\system\test_role_based_routing.py -q`
- `python -m py_compile src/ai/agents/__init__.py src/ai/agents/business_analyst_agent.py src/ai/agents/qa_engineer_agent.py src/ai/mcp/multi_role.py src/ai/role_based_router.py tests/unit/test_multi_role_agents_evidence_contract.py`
