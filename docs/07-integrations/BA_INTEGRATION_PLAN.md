# BA Интеграционный план (Sprint 3)

## 1. Цели

- Обеспечить двусторонние интеграции BA-модуля с Jira, Confluence/Notion, Power BI/Яндекс DataLens и 1С:Документооборот.
- Настроить совместную работу команды (multi-user session), аудит и контроль доступа.
- Гарантировать соответствие требованиям безопасности (152-ФЗ, GDPR), наличие журналов и SLA.

## 2. Базовая архитектура

- **BA Core** (FastAPI + AI агенты) ↔ **Integration Layer** (коннекторы).
- **Data Foundation**: `data/ba_intel` + knowledge graph (PostgreSQL/Neo4j/Qdrant).
- **Security**: OAuth2/Service Accounts, Secrets Manager, DLP & logging.

```
Users → BA UI/API → BA Core Agents
                    ↘ Integration Layer →
                        • Jira REST
                        • Confluence/Notion API
                        • BI (Power BI/DataLens)
                        • 1С:Документооборот (HTTP/COM)
```

## 3. Интеграции и требования

### 3.1 Jira (Project/Task Sync)
- **Use cases**: создание epic/story из discovery, обновление статуса, импорт существующих задач.
- **Точки интеграции**: REST API (`/rest/api/3/issue`), webhooks (status change).
- **Аутентификация**: OAuth 2.0 (preferred) или PAT, хранение в Secrets Manager.
- **Артефакты**:
  - Mapping: BA requirement → Jira Epic/Story/Subtask.
  - Шаблоны issue (labels: `source:ba`).
- **Аудит**: логируем каждое создание/обновление (`integration_logs/jira_*`).
- **Failover**: ретраи с экспоненциальной паузой, DLQ (JSON snapshot).

### 3.2 Confluence / Notion (Documentation Sync)
- **Use cases**: публикация discovery canvas, BPMN диаграмм, roadmap, автогенерация wiki.
- **API**: Confluence Cloud REST (`/wiki/api/v2/pages`), Notion REST (блоки).
- **Формат**: Markdown/HTML, вложения (Mermaid renders, PDF).
- **Security**: service accounts, ACL (read: team, edit: BA).
- **Automation**: `scripts/ba_integration/publish_docs.py`.

### 3.3 BI (Power BI / Yandex DataLens)
- **Use cases**: обновление dataset, запуск refresh, получение ссылок для презентаций.
- **API**:
  - Power BI REST: dataset refresh (`POST /refreshes`), export report.
  - DataLens API: dataset refresh, dashboard embed link.
- **Data pipeline**: выгрузка BA metrics → staging → BI dataset.
- **Security**: managed identities, IP allow-list, tokens в Secrets Manager.
- **Monitoring**: SLA refresh < 10 минут, уведомления (Slack/Teams).

### 3.4 1С:Документооборот
- **Use cases**: регистрация документов discovery, согласование roadmap, хранение договорённостей.
- **API**: HTTP сервисы 1С (JSON), COM-обёртка (при необходимости).
- **Tasks**:
  - Конвертация артефактов (docx/pdf).
  - Привязка к карточкам (Проект, Встреча).
- **Security & Audit**: права доступа (роль «BA Integration»), журнал всех insert/update.
- **Resilience**: retry + очередь (RabbitMQ/Kafka при высоком трафике).

## 4. Совместные сессии и collaboration

- **Multi-user session**: WebSocket/SignalR канал → синхронизация state (agenda, заметки).
- **Locking**: optimistic merge, history log (diffs).
- **Feedback**: встроенная форма → `scripts/ba_internal/feedback_collector.py`.
- **Scheduling**: интеграция с календарём (ICS в 1С/Outlook).

## 5. Безопасность и соответствие

- **Аутентификация**: OAuth/OIDC, short-lived tokens, refresh policies.
- **Авторизация**: RBAC (roles: BA Lead, Analyst, Reviewer, Viewer).
- **DLP**: маскирование PII, контроль выгрузок (Power BI export restricted).
- **Audit trail**: централизованный лог (`security/audit/ba_integrations.log`), сохранение 12 мес.
- **Compliance**: 152-ФЗ, GDPR — checklists, ежегодные ревизии, DPIA.

## 6. SLA & Monitoring

| Интеграция | SLA | Мониторинг | Аварийный план |
|------------|-----|------------|----------------|
| Jira | latency < 3s, success ≥ 99% | Prometheus + alerts | Retry, fallback to CSV |
| Confluence/Notion | publish < 60s | Cloud logs, Slack alerts | Уведомление + ручной экспорт |
| Power BI/DataLens | refresh < 10 min, success ≥ 98% | API status, dashboards | Ручной restart + уведомление |
| 1С:Документооборот | sync < 2 min | 1С ping, лог ошибок | Очередь, ручное вмешательство |

## 7. План реализации (итерации)

1. **I1**: Jira + Confluence (REST клиент, CLI, тесты).  
2. **I2**: Power BI/DataLens (refresh, embed, SLA мониторинг).  
3. **I3**: 1С:Документооборот (HTTP wrapper, очереди).  
4. **I4**: Multi-user session, audit, security hardening.  
5. **I5**: End-to-end тесты, FMEA, документация (runbooks).

## 8. Тестирование

- Unit tests: моки REST, сериализация payload.
- Integration tests: sandbox окружения Jira/Confluence/BI, 1С test контур.
- E2E: сценарий discovery → issue → wiki → BI → Document → отчет.
- Chaos / resilience: имитация недоступности API, проверка fallback.

## 9. Документация и процессы

- Обновить `docs/06-features/BUSINESS_ANALYST_GUIDE.md` → раздел Sprint 3.
- Подготовить runbooks (`docs/runbooks/ba_integrations/*.md`).
- Конфигурация (Vault/Secrets): `BA_JIRA_TOKEN`, `BA_CONFLUENCE_TOKEN`, `BA_POWERBI_CLIENT_ID`, `BA_1C_URL` и т.д.
- CI/CD: GitHub Actions/TeamCity – прогон unit/integration тестов, деплой коннекторов.

