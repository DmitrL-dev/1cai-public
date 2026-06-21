# Security Offline Contracts

Дата: 2026-06-20.

## Зачем

Security/CVE/LLM слой не должен показывать пустые списки как доказательство безопасности. Для enterprise-покупателя честное `not measured` лучше, чем ложный green check.

## Что сделано

- `src.ai.llm` получил baseline `AdaptiveLLMSelector` offline fallback вместо падения на отсутствующем `adaptive_selector`.
- `SecurityAgent` теперь импортируется в baseline и отличает real LLM от offline fallback.
- Dependency audit помечает отсутствие CVE источника как `coverage: no_cve_database`, `vulnerability_measured: false`.
- SAST без инструмента возвращает `local_regex_security_scan` с caveat, а не полноценный SAST.
- DAST без инструмента возвращает `needs_configuration` и `findings_measured: false`.
- `CVEDatabaseClient` больше не объявляет OSV initialized через фиктивный `True`.

## Проверка

- `pytest tests\unit\test_security_offline_contract.py -q`
- `python -m py_compile src/ai/llm/__init__.py src/ai/agents/security_agent.py src/integrations/cve_database_client.py tests/unit/test_security_offline_contract.py`
