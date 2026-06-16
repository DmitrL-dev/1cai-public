# Business Analyst Module Guide (2025 Roadmap)

## 1. Цель и охват

- Сформировать «digital twin» команды бизнес-аналитиков (уровень Senior/Lead) в экосистеме 1С.
- Синхронизировать процессы с BABOK v3, PMI-PBA, отраслевыми регуляториками (152‑ФЗ, GDPR).
- Поддерживать полный цикл: discovery → анализ → моделирование → delivery → оценка эффекта.

## 2. Рынок и тренды 2025

### 2.1 Россия
- **1С как ядро**: 1С:ERP, 1С:Управление торговлей, 1С:ЗУП, 1С:Документооборот, 1С:BI.
- **Интеграции**: REST/GraphQL API, OData, Kafka/RabbitMQ, интеграция с SAP, CRM, ГосСистемами.
- **Data & BI**: PostgreSQL/ClickHouse, Power BI, Яндекс DataLens, Python (pandas, scikit-learn), ETL (Airflow, 1С:Аналитик).
- **Управление процессами**: BPMN 2.0, UML, IDEF0, Camunda/ELMA, BABOK техники (impact mapping, story mapping).
- **Compliance**: 152‑ФЗ, ФЗ-54, НДС/РСБУ, отраслевые стандарты (банки, ритейл, производство).

### 2.2 Зарубеж
- **Product analytics**: SQL + Python/R, Looker/Mode, Mixpanel, Amplitude, experimentation platforms.
- **Cloud & governance**: AWS/GCP/Azure, data catalogs, GDPR, CCPA, ISO 27001.
- **AI adoption**: чат-ассистенты, генерация требований, predictive analytics для KPI.
- **Delivery**: dual-track Agile, OKR, discovery vs delivery balance, stakeholder storytelling.

### 2.3 Топ компетенций (объединённый список)
- Системное/критическое мышление, умение отделять важное от неважного.
- Навыки коммуникации: интервью, фасилитация, аргументация решений.
- Техническая база: BPMN/UML/IDEF0, ER/EPC, SQL, REST API, Python для анализа данных.
- Продуктовое мышление: data-driven decisions, визуализация (DataLens, Power BI), A/B тесты.
- Знание предметной области: финансы, ритейл, производство, логистика, госуслуги.

## 3. BABOK Coverage

| BABOK Knowledge Area | Что делаем в модуле | Автоматизация |
|----------------------|---------------------|---------------|
| Business Analysis Planning & Monitoring | Roadmap, stakeholder map, RACI, risk register | Digital BA Lead, шаблоны планов |
| Elicitation & Collaboration | Интервью, воркшопы, customer journey | Discovery Agent, симуляторы Q&A |
| Requirements Life Cycle Management | Трейсинг требований, контроль версий | Jira/Confluence sync, requirement graph |
| Strategy Analysis | Анализ бизнес-кейса, SWOT, value tree | AI-ассистент «Strategy deck» |
| Requirements Analysis & Design Definition | BPMN/UML/IDEF0, prototyping, scenario mapping | Process Modeler Agent, генератор диаграмм |
| Solution Evaluation | KPI, ROI/NPV, hypothesis validation | BI интеграции, outcome dashboards |

## 4. Матрица навыков (уровни)

| Направление | Junior | Middle | Senior / Lead |
|-------------|--------|--------|---------------|
| **Аналитика** | Сбор требований, фин. отчёты 1С | Формализация процессов, gap-анализ | Архитектура процессов, бизнес-стратегия |
| **Коммуникации** | Интервью по шаблону | Фасилитация встреч, защита решений | Управление стейкхолдерами, переговоры C-level |
| **Технические навыки** | Основы SQL, BPMN, 1С отчёты | API/интеграции, UML/IDEF0, 1С:EDT | Портфель интеграций, выбор архитектуры, CI/CD 1С |
| **Продуктовые навыки** | KPI awareness, dashboards | A/B тесты, продуктовые метрики | Data-driven стратегия, экономическое обоснование |
| **Доменные знания** | Базовые процессы компании | Отраслевые особенности | Мультиотраслевые решения, комплаенс |

## 5. Инструментальный стек

- **1С & Automation**: 1С:Enterprise 8.3/8.3.22, 1С:EDT, Git/CI, 1С:BI, 1С:Документооборот, 1С PM.
- **Modeling**: Camunda Modeler, Bizagi, draw.io, Miro, PlantUML, Mermaid.
- **Data/BI**: PostgreSQL, ClickHouse, Greenplum, Power BI, Tableau, Yandex DataLens, Apache Superset.
- **Analytics & AI**: Python (pandas, numpy, Prophet), AutoML (H2O, Vertex AI), OpenAI/Anthropic, MLFlow.
- **Collaboration**: Jira, Confluence, Notion, Slack/Teams, GitHub, Azure DevOps.
- **Compliance/Security**: IAM (Keycloak, Azure AD), DLP, audit trails, шифрование артефактов.

## 6. Digital BA Squad (Senior-Level)

- **Digital BA Lead**: управляет roadmap, согласует стейкхолдеров, проводит ревью.
- **Discovery Agent**: задаёт вопросы, оформляет требования, выявляет риски.
- **Process Modeler Agent**: строит BPMN/UML/IDEF0, проверяет целостность, готовит диаграммы.
- **Data Analyst Agent**: SQL/BI отчёты, копает KPI, генерирует инсайты в DataLens/Power BI.
- **Domain Expert Agent**: знание 1С-платформы, отраслей, регуляторики, 152‑ФЗ/GDPR.
- **Communication Coach**: готовит презентации, сценарии переговоров, сторителлинг.

### 6.1 Storytelling & Integrations

- **Storytelling Coach**:
  - Формирует презентации/доклады: outline, narrative, визуальные подсказки под разные аудитории (executive/product/tech).
  - Подготавливает сценарии выступлений и демо: agenda, talking points, Q&A, demo flow.
  - Поддерживает шаблоны storytelling-паттернов (Problem → Solution → Value → Next steps).
  - При наличии настроенных LLM (GigaChat, YandexGPT, OpenAI) уточняет материалы, добавляя рекомендации.
  - Синхронизирован с Digital BA Lead: использует стратегию, KPI, roadmap и риски.
- **Integration Connector** (каркас):
  - Jira: постановка эпиков/тасков на основе требований/roadmap (требуется настройка REST API).
  - Confluence/Notion: публикация артефактов (требования, диаграммы, презентации).
  - BI (Power BI, Яндекс DataLens): подготовка заметок к обновлению дашбордов, интеграция с dataset (предстоит реализовать).
  - 1С:Документооборот: синхронизация документов по инициативам (требует endpoint + токен).
  - Возвращает статусы интеграции, логирует ошибки, предупреждает об отсутствии конфигурации.

### 6.2 Совместные сессии и аудит
- WebSocket `ws://<host>/ba-sessions/ws/{session_id}` с параметрами `user_id`, `role`, `token`.
- Менеджер сессий (`src/services/ba_session_manager.py`): хранит участников, историю, audit trail (`logs/audit/ba_sessions.log`).
- Типы событий: `chat`, `artefact_update`, `system`, `private`. Каждый шаг фиксируется для compliance.
- REST API (`GET /ba-sessions`, `GET /ba-sessions/{id}`) — состояние и активные комнаты.
- Метрики Prometheus: `ba_ws_active_sessions`, `ba_ws_active_participants`, `ba_ws_events_total{event_type}`, `ba_ws_disconnects_total{reason}`, `ba_ws_audit_failures_total`.
- Runbook и тестовая матрица: `docs/08-e2e-tests/BA_E2E_MATRIX.md`.

### Возможности «живой» команды
- Auto-briefings: генерация summary, risk register, agenda на встречи.
- Scenario simulator: тренировочные воркшопы (интервью, совместное моделирование).
- Review mode: Digital Lead оценивает артефакты, выдаёт feedback по BABOK/хардам/софтам.
- Stakeholder alignment: автоматическое формирование RACI, план коммуникаций, стратегии эскалации.

## 7. План реализации

### Спринт 0 — Data Foundation
- Настроить пайплайн автоматического сбора данных (job market, резюме, конференции, регуляторика) — запуск первых скриптов из Приложения A.
- Поднять хранилище знаний (Neo4j/PostgreSQL/Qdrant) и ETL/качество данных.
- Создать дашборды мониторинга источников (coverage, freshness).
- Разместить документацию по запуску скриптов (`docs/operations/ba_data_pipeline.md`), интегрировать в CI.

### Спринт 1 — Foundations
- Обновить гайд (этот документ), добавить ссылки на BABOK, матрицу компетенций.
- Подготовить assessment-формы: self-check, knowledge quiz, gap analysis.
- Создать библиотеку шаблонов (интервью, user story, impact mapping, BPMN/UML/IDEF0 файлы).
- Встроить испытательный сценарий discovery → процесс → BI (1С + DataLens).
- Связать assessment/шаблоны с обновляемым knowledge graph (данные из Спринта 0).

### Спринт 2 — AI & Simulation
- Реализовать Digital BA Lead с возможностью ревью и рекомендаций.
- Запустить Discovery Agent и Process Modeler Agent (симуляция интервью, авто-диаграммы).
- Настроить Storytelling/Communication Coach (презентации, демо, обоснования).
- Добавить автоматические проверки BABOK (coverage, traceability, completeness) и обновление трендов из pipelines.

### Спринт 3 — Интеграции и командная работа
- Интеграция с Jira/Confluence/Notion, 1С:Документооборот, Power BI/DataLens.
- Поддержка совместных сессий (multi-user + digital agents, чат, whiteboard API).
- Analytics & Monitoring: автоматический сбор метрик (time-to-insight, adoption, NPS).
- Compliance layer: audit logs, настройка DLP, role-based access.
- Детальный план и требования: `docs/07-integrations/BA_INTEGRATION_PLAN.md`.
- Автоматическая синхронизация интеграций и storytelling (триггеры от pipelines, уведомления).

## 8. Шаблоны и оценка

- **Assessment**: check-лист по BABOK, матрица hard/soft/product skills, тесты SQL/BPMN.
- **Артефакты**: шаблоны discovery-интервью, user story (INVEST), acceptance criteria, OKR/roadmap, документы 1С.
- **Automated feedback**: парсеры диаграмм, scoring компетенций, рекомендации по развитию.
- **Storytelling**: генераторы презентаций, сценариев, визуальных подсказок, Q&A.
- **Интеграции**: набор коннекторов Jira/Confluence/BI/1С, отчёты о синхронизациях.
- **Assessment**: self-check формы, BABOK quiz, выявление gap по навыкам.
- **Сценарии**: discovery → процесс → BI (1С + DataLens/Power BI), включая чек-листы.

## 9. Метрики успеха

- Time-to-insight (время от запроса до артефакта).
- Доля автоматически сгенерированных артефактов, принятых без правок <5%.
- Повышение NPS внутренних пользователей (аналитики, product owners).
- Сокращение времени согласования требований/процессов (baseline vs target).
- Coverage & Freshness: доля актуализированных навыков в knowledge graph (обновление ≤14 дней).
- Pipeline Reliability: процент успешных запусков data-пайплайна (>95%), задержки по источникам.

## 10. Интеграции и безопасность

- Подключение к корпоративным системам: 1С, Jira, Confluence, BI, CMDB, DWH.
- Шифрование конфиденциальных данных, разграничение доступа, mask PII.
- Логи действий digital-агентов, explainability для AI-инсайтов.
- Проверка на соответствие 152‑ФЗ, GDPR, корпоративным стандартам (audit ready).

## Приложение A. Автоматизация обновления знаний

| Направление | Скрипт / задача | Описание | Периодичность |
|-------------|-----------------|----------|---------------|
| Вакансии (РФ, зарубеж) | `scripts/ba_market/hh_scraper.py`, `scripts/ba_market/linkedin_scraper.py`, `scripts/ba_market/indeed_scraper.py` | Сбор вакансий (hh.ru, SuperJob, Habr Career, Geekjob, LinkedIn, Indeed, Glassdoor) с классификацией компетенций, стеков, уровней | Еженедельно |
| Резюме / профили | `scripts/ba_market/resume_parser.py` | Парсинг открытых резюме и профилей BA, выделение фактических навыков | Ежемесячно |
| Конференции / стандарты | `scripts/ba_intel/conference_digest.py`, `scripts/ba_intel/standard_tracker.py` | Сбор докладов Analyst Days, IIBA, PMI; мониторинг обновлений BABOK, PMI-PBA, ISO, отраслевых регламентов | Ежеквартально |
| Отчёты консультантов | `scripts/ba_intel/consulting_digest.py` | Выжимка отчётов Gartner, McKinsey, Accenture, Bain по BA/analytics | Ежеквартально |
| Образование | `scripts/ba_intel/education_monitor.py` | Мониторинг syllabus программ (Netology, OTUS, Coursera, университеты) | Ежеквартально |
| Регуляторика | `scripts/ba_compliance/regulation_watcher.py` | Отслеживание изменений 152‑ФЗ, GDPR, отраслевых требований (ЦБ, ISO 33014) | Еженедельно |
| Внутренние артефакты | `scripts/ba_internal/artefact_ingest.py` | Ингест требований, BPMN, отчётов проектов 1С в knowledge graph | При каждом релизе |
| Feedback loop | `scripts/ba_internal/feedback_collector.py`, `scripts/ba_internal/nps_survey.py` | Сбор отзывов BA (анкеты, NPS, feedback widget), аналитика запросов | Ежемесячно |
| Использование модуля | `scripts/ba_internal/usage_analytics.py` | Аналитика вызовов BA-агента, SLA, востребованности функций | Еженедельно |
| Конкуренты | `scripts/ba_competitive/feature_matrix.py` | Матрица сравнения с SAP Signavio, IBM Blueworks, Oracle BPM, Salesforce, отечественными решениями | Ежеквартально |
| Knowledge Graph | `scripts/ba_knowledge/update_graph.py` | Обновление Neo4j/PostgreSQL/Qdrant графа навыков, трендов, артефактов | После каждого сбора данных |
| Assessment & Skills | `scripts/ba_assessment/generate_forms.py` | Обновление self-check/quiz форм, матрицы компетенций на основе свежих данных | Ежеквартально |
| Scenario Library | `scripts/ba_scenarios/sync_templates.py` | Поддержание сценариев discovery → процесс → BI, шаблонов интервью, acceptance | Ежемесячно |
| Оркестрация | `scripts/ba_orchestrator/run_all.py` | Пайплайн (Airflow/Prefect) для запуска всех сборщиков, контроль расписаний | По cron/CI |
| Data Quality | `scripts/ba_quality/check_dataset.py` | Проверка качества данных (skills coverage, дубликаты, устаревшие записи) | После каждого обновления |

Требования к автоматизации:
- Логирование и сохранение снапшотов (JSON/CSV) в `data/ba_intel/`.
- Обновление knowledge graph (Neo4j/Qdrant/PostgreSQL) и кэша BA-агента.
- Поддержка `.env` и секретов (API keys, rate limits), уведомления об ошибках (Slack/Teams/email).
- Unit/integration тесты (`tests/scripts/test_*`), mock внешних API.
- Интеграция в CI/CD (GitHub Actions, Jenkins) с расписанием.

---

**Дальнейшие шаги:** реализовать data foundation (Спринт 0), assessment и шаблоны, затем перейти к разработке Digital BA Lead, симуляторов и интеграций согласно плану спринтов. Повторять обновление знаний по расписанию, контролируя метрики покрытия и надёжности пайплайнов.

