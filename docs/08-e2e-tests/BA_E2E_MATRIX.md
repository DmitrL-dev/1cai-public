# BA End-to-End Test & Runbook (Sprint 3)

## 1. Цели

- Проверить сквозные сценарии BA-модуля с учётом интеграций (Jira, Confluence/Notion, Power BI/DataLens, 1С:Документооборот).
- Убедиться, что совместные сессии (multi-user) и audit trail работают корректно.
- Подготовить runbook для ручного и автоматизированного запуска.

## 2. Обзор сценариев

| ID | Сценарий | Описание | Зависимости |
|----|----------|----------|-------------|
| E2E-01 | Discovery → Jira | Проведение discovery-сессии, автоматическое создание Jira tickets | Jira, DiscoveryAgent, IntegrationConnector |
| E2E-02 | Process → Confluence | Генерация BPMN/roadmap, публикация в Confluence | ProcessModeler, Storytelling, Confluence |
| E2E-03 | Metrics → Power BI | Обновление BI dataset и проверка дашборда | PowerBIClient, scripts/ba_integration |
| E2E-04 | Docs → 1С | Регистрация документа в 1С:Документооборот | OneCDocflowClient |
| E2E-05 | Multi-user Session | Совместная работа BA Lead + Analyst (websocket) | Session service, audit trail |
| E2E-06 | Offline Mode | Переключение LLM на локальный backend | LLM Gateway, role router |
| E2E-07 | Failover Integrations | Обработка ошибок (Jira/Confluence недоступны) | IntegrationConnector, alerting |

## 3. Тестовая матрица

| Сценарий | Step | Ожидание | Проверка |
|----------|------|----------|----------|
| E2E-01 | Run `scripts/ba_integration/sync_artifact.py` с discovery artefact | Jira issue создан, лейбл `source=ba` | Jira API/get issue |
| | Update issue via BA agent | Статус обновлён | Jira GET |
| E2E-02 | Process simulation → storytelling deck | Artefact JSON содержит диаграмму + narrative | JSON assert |
| | Sync artefact to Confluence | Страница создана, ссылка доступна | Confluence API |
| E2E-03 | Trigger Power BI refresh | API возвращает 202, job завершился | PowerBIClient.monitor job |
| | Проверить KPI | Dashboard отражает обновлённые значения | Manual/automated screenshot |
| E2E-04 | Sync document | Документ зарегистрирован в 1С | API response, log |
| E2E-05 | Открыть совместную сессию | Оба пользователя видят изменения и чат | Websocket events, audit records |
| | Разорвать соединение одного клиента | Остальные участники получают уведомление | Websocket state |
| E2E-06 | Отключить OpenAI | Router переключается на локальный backend | Prometheus metric, BA responses |
| | Запустить smoke-тесты | Ключевые запросы выполняются | `tests/integration/test_llm_failover.py` |
| E2E-07 | Симулировать ошибку интеграции | Лог + alert, retry/queued статус | Connector response, alertmanager |

## 4. Runbook (автоматический запуск)

```bash
make e2e-prepare   # проверка переменных окружения, токенов
make e2e-run       # запускает набор pytest + сценарии sync_artifact
make e2e-report    # собирает отчёт в docs/08-e2e-tests/reports/
```

### make e2e-run (псевдо)

```Makefile
e2e-run:
	python -m pytest tests/integration/test_ba_session.py -v
	python -m pytest tests/integration/test_llm_failover.py -v
	python scripts/ba_integration/sync_artifact.py artefacts/discovery.json --targets jira
	python scripts/ba_integration/sync_artifact.py artefacts/process_deck.json --targets confluence powerbi
```

## 5. Мониторинг и алерты

- **Prometheus** (`/metrics`):  
  - `ba_ws_active_sessions`, `ba_ws_active_participants` — активность комнат/людей.  
  - `ba_ws_events_total{event_type}` — события (`join`, `chat`, `leave`, `session_closed`, `private`, `system`).  
  - `ba_ws_disconnects_total{reason}` — отвалившиеся клиенты (`send_error`, `manual_close`).  
  - `ba_ws_audit_failures_total` — ошибки записи audit trail (должно быть = 0).  
  - `integration_status{system}`, `llm_provider_status` — статус интеграций и LLM.  
- **Alertmanager** (`monitoring/prometheus/rules/ba_sessions.yml`):  
  - `BAWebsocketDown` — ноль активных сессий при запланированном слоте > 5 минут.  
  - `BAAuditErrors` — рост `ba_ws_audit_failures_total` за последние 10 минут.  
  - `IntegrationFailure`, `LLM_Failover_Active` — существующие правила.  
- **Grafana**: `monitoring/grafana/dashboards/ba_sessions.json` (совместные сессии) + `ba_integrations.json`.

## 6. Multi-user Session & Audit

- WebSocket endpoint `/ba-sessions/ws/{session_id}` (query: `user_id`, `role`, `token`, `topic`).  
- REST: `GET /ba-sessions`, `GET /ba-sessions/{id}` — список комнат и состояние.  
- Audit log: `logs/audit/ba_sessions.log`, один JSON на событие.  
- Role-based access (`BA Lead`, `Analyst`, `Reviewer`, `Observer`).  
- При reconnect участник получает актуальную историю (последние 200 событий).

## 7. Chaos & Failover

- Использовать `tests/integration/test_llm_failover.py` для симуляции отключения внешних LLM.
- Chaos scripts:  
  - `scripts/chaos/block_jira.sh` (iptables или AWS WAF rule)  
  - `scripts/chaos/kill_ws_node.sh`
- Post-test checklist: фиксация времени на восстановление, оценка влияния на пользователей.

## 8. Артефакты отчётности

- `docs/08-e2e-tests/reports/E2E_RUN_<timestamp>.md`  
  - резюме: успешные/проваленные сценарии, ссылки на артефакты.
- Confluence/Notion: страница с short report и ссылкой на logs.
- Jira Epic: `BA-E2E` — тикеты на устранение выявленных проблем.

## 9. Расписание

- **Еженедельно**: автоматический e2e-run (ночью, cron CI).
- **Перед релизом**: ручной запуск + review отчёта.
- **После регрессий**: обязательная проверка E2E-01…E2E-04.

---

**Статус:** матрица и runbook подготовлены, готово к реализации сценариев и конфигурации CI/CD.

