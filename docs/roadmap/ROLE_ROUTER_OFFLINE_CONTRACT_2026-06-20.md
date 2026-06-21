# Role Router Offline Contract

Дата: 2026-06-20.

## Зачем

Ролевой маршрутизатор был опасен для демонстрации: при недоступности внешних агентов он возвращал `agent: "placeholder"` и тексты вида "integration pending". Для клиента это выглядит как незаконченный AI-чат, а не как локальный инженерный control plane.

## Что сделано

- Убран `placeholder` из fallback-веток `RoleBasedRouter`.
- Добавлен единый локальный контракт `offline_role_router`.
- Fallback теперь возвращает роль, режим, coverage, recommended actions, required evidence, context keys, unavailable integrations и caveats.
- Архитектурная ветка больше не притворяется `openai-gpt4`, если внешнего архитекторского агента нет.
- Имена активных агентов приведены к реальным контрактам: `business_analyst_agent`, `qa_engineer_agent`, `devops_agent`, `technical_writer_agent`.
- Если `qwen3-coder` падает во время генерации, роутер деградирует в тот же честный локальный контракт.

## Проверка

- `pytest tests\unit\test_role_based_router_contract.py tests\system\test_role_based_routing.py -q`
- `python -m py_compile src/ai/role_based_router.py tests/unit/test_role_based_router_contract.py`
- `rg` по ролевому роутеру больше не находит `placeholder`, `integration pending` и старые `*_extended` имена.
