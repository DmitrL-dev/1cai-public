# Deep product research: 1cAI / 1C Copilot platform

Дата среза: 2026-06-15.

Цель: понять, чего не хватает 1cAI до сильной enterprise-платформы полного цикла разработки 1C, сравнив нас с официальной 1C-экосистемой, open-source 1C-инструментами, AI-copilot рынком, low-code/ALM/DevOps продуктами и BA/governance решениями.

## TL;DR

Рынок не пустой. В 1C уже есть EDT, Конфигуратор, хранилище, пакетный режим, АПК, тестирование, ИТС, БСП и корпоративные инструменты. В сообществе уже есть BSL Language Server, SonarQube BSL, Vanessa/YAxUnit, OneScript/OPM, v8unpack, gitsync/GitConverter, MCP-серверы. В enterprise-мире уже есть GitHub Copilot, GitLab Duo, Sourcegraph, Cursor, JetBrains Junie, Amazon Q, SAP Joule, ServiceNow App Engine, Power Platform, Azure DevOps, Polarion, DOORS, Sparx, TestRail/Xray.

Главная дыра рынка для 1C не в генерации кода. Дыра в едином on-prem 1C-native control plane, который связывает требования, архитектуру, метаданные, BSL, формы, роли, права, регистры, запросы, тесты, релизы, approvals, CI/CD, эксплуатационные инциденты и риск изменения. Generic copilots видят текст, но не видят конфигурацию как живую систему. Официальные и community-инструменты дают мощные кирпичи, но не дают единую систему управления жизненным циклом.

Позиционирование 1cAI: не "еще один чат для BSL", а внутренняя система истины и риск-движок разработки 1C. AI должен быть верхним слоем. Даже без подключенного AI продукт обязан приносить ценность: граф конфигурации, impact/blast radius, dead code, quality hotspots, policy gates, traceability, release readiness, test selection, approvals, CI artifacts, dashboards.

## Продуктовая формула

1cAI должен стать:

1. **1C-native engineering graph**: единая модель конфигурации, кода, метаданных, форм, ролей, регистров, запросов, расширений, тестов, требований, релизов и инцидентов.
2. **Deterministic governance core**: правила, gates, approvals, baselines, change sets, evidence, audit trail. Работает без LLM.
3. **Adapter/orchestration layer**: EDT CLI, Конфигуратор, АПК, BSL LS, Sonar, YAxUnit, Vanessa, OneScript, v8unpack, GitLab/GitHub/Jenkins, EDT-MCP.
4. **Agentic UX on top**: Ask / Plan / Act / Review, где агент не меняет критичные артефакты без плана, diff, проверок и approval.
5. **On-prem by design**: закрытый контур, локальные индексы, локальная модель опционально, сетевые вызовы под политикой.

## Официальная 1C-экосистема

| Область | Что уже есть | Вывод для 1cAI |
|---|---|---|
| IDE | 1C:EDT: проекты в файловой системе, Git, несколько конфигураций/расширений/внешних обработок, проверки, редакторы BSL/запросов/RLS | Не конкурировать с EDT как IDE. Делать bridge/control plane поверх EDT и его CLI. |
| Классическая разработка | Конфигуратор, хранилище, сравнение/объединение, поставка, поддержка, пакетный режим | Поддерживать legacy-команды, где Git/EDT еще не внедрены. |
| CI/automation | EDT CLI, `.1cedtcli`, пакетный Конфигуратор, 1C:Исполнитель | Строить pipeline-оркестратор, а не свой раннер с нуля. |
| Quality | Встроенная проверка конфигурации, 1C:АПК | Импортировать findings в единый quality gate. |
| Testing | Платформенное автотестирование, 1C:Тестировщик, 1C:Сценарное тестирование | Добавить test evidence, selection by impact, flaky/history. |
| Методология | ИТС, стандарты разработки, БСП, СППР | Делать standards/RAG/правила с citations и привязкой к месту в коде. |
| Enterprise ops | 1C:Управление ландшафтом | Для крупных клиентов интегрироваться, но не делать его обязательной зависимостью. |

Сильное место 1C: глубокая доменная платформа и официальная цепочка от разработки до сопровождения. Слабое место: фрагментация. Разработчик живет между EDT, Конфигуратором, хранилищем, Git, ИТС, АПК, тестами, внешним CI и продуктивными ИБ. 1cAI должен стать объединяющим слоем.

## Open-source и community 1C

| Инструмент | Что закрывает | Что брать |
|---|---|---|
| BSL Language Server | LSP, diagnostics, formatting, navigation, references, call hierarchy, complexity, CLI analyze/format, reporters | Адаптер диагностики и символов. Не переписывать 180+ правил с нуля. |
| SonarQube BSL plugin | Quality dashboard, rules, duplication, metrics, CI quality gates | Экспорт findings 1cAI в Sonar Generic Issue/SARIF-like формат и импорт Sonar findings обратно. |
| Vanessa Automation / Vanessa ADD | BDD/UI/regression, feature scenarios, autodoc | Генерация сценариев из требований, запуск, evidence, привязка к change set. |
| YAxUnit + EDT Test Runner | Unit tests, assertions, EDT запуск/отладка | Генерация и запуск unit-тестов, coverage matrix, affected tests. |
| OneScript + OPM | Скрипты сборки, DevOps, package ecosystem | Поддержка `packagedef`, запуск oscript-задач, dependency inventory. |
| EDT-MCP / mcp-1c | Контекст EDT/живой базы для AI tools | MCP adapters как штатный интерфейс 1cAI. Read-only default, write tools через approvals. |
| precommit1c / precommit4onec | Git-friendly unpack/build checks | `1cai-precommit`: unpack sanity, BSL LS, secrets, metadata schema, индекс контекста. |
| v8unpack / metadata tools | `.cf/.epf/.erf` unpack/pack/parse/build | Canonical metadata adapter: EDT XML/v8unpack/JSON/live DB -> единая модель. |
| vanessa-runner / v8runner / Jenkins plugins | CI wrappers for 1C | Готовые pipeline templates и self-hosted runner profiles. |
| gitsync / GitConverter | Хранилище -> Git/EDT, перенос истории | Импорт истории в graph: авторы, объекты, ветки, теги, impact по изменениям. |

Правило: низкий уровень не переписываем, если уже есть зрелый инструмент. 1cAI выигрывает как оркестратор, нормализатор и система решений поверх этих результатов.

## AI-copilot рынок

| Продукт | Сильный паттерн | Что нужно перенять |
|---|---|---|
| GitHub Copilot Enterprise | Issue -> branch -> code changes -> PR; code review suggestions | Задача/change request -> план -> ветка/изменение -> тестовая ИБ -> MR/PR -> review. |
| GitLab Duo | AI встроен в DevSecOps, code review, CI RCA, agent platform | RCA падений 1C pipeline, review flow, AI в release gate. |
| Sourcegraph Cody | Whole-codebase context, multi-repo context, RBAC/context filters | Multi-config/multi-repo 1C graph с фильтрами доступа. |
| Cursor | Plan Mode, Rules, Cloud Agents, BugBot, Privacy Mode | Project/team rules, Plan before Act, background tasks, privacy controls. |
| JetBrains Junie | Агент в IDE меняет файлы и запускает проверки | EDT-native agent UX: visible plan/progress/checks. |
| Amazon Q Developer | `/doc`, `/test`, `/review`, modernization agents, security scan | Модернизационные агенты: обновление типовой, перенос старых форм, рефакторинг запросов. |
| SAP Joule / Build | Доменный copilot для SAP-разработки и ABAP-aware оптимизации | Для 1C важнее доменная модель платформы, чем generic code chat. |
| Power Platform Copilot | Natural language -> app + data model + flows | "Бизнес-процесс -> 1C artifacts": справочники, документы, регистры, формы, роли, отчеты. |
| ServiceNow App Engine / Now Assist | Plain language -> workflows/apps/tests with governance/change controls | Разговорное создание изменения плюс встроенный change control. |

Главный вывод: AI-лидеры ушли от autocomplete к agentic workflow. Но все generic-продукты слабы для 1C, потому что 1C-ошибка часто живет не в строке BSL, а в связке "метаданные -> права -> форма -> запрос -> регистр -> проведение -> обмен -> версия платформы -> тестовая ИБ".

## Enterprise SDLC, DevOps, ALM

| Capability | Что enterprise считает нормой | Что должно быть в 1cAI |
|---|---|---|
| ALM | Intake, work items, requirements, docs, owners, releases | Внутренний ALM core, не зависимый от Jira/ADO. |
| Git/source control | Branches, PR/MR, protected branches, status checks | PR/MR decoration, status checks, diff risk report. |
| CI/CD | Build/test/package/deploy, artifacts, gates | Готовые GitHub/GitLab/Azure/Jenkins templates для 1C. |
| Quality gates | Baseline, threshold, fail/warn, waivers | Policy & Gates Engine с audit evidence. |
| AppSec | SAST/SCA/secrets/SBOM/license | Adapters к Semgrep/Snyk/Mend или локальные equivalents; 1C-specific secrets/risky patterns. |
| IAM/governance | SSO, SCIM/LDAP, RBAC, audit streaming, SoD | Enterprise IAM layer и SIEM export. |
| Test management | Cases, suites, runs, evidence, defects | Verification layer поверх YAxUnit/Vanessa/1C Test tools. |
| Change management | CR, approvals, deployment pause/resume, rollback | Change sets как центральный объект. |
| Portfolio | App catalog, ownership, tech debt, risk dashboards | Manager/architect cockpit по конфигурациям и подсистемам. |
| Metrics | DORA, MTTR, lead time, change failure rate | DORA/ops dashboards, incident-to-code feedback loop. |

## BA, requirements, architecture

BA-слой должен быть внутренним. Внешние Jira, Confluence, DOORS, Polarion, Miro, TestRail и Azure DevOps нужны как adapters/sync при оплате и внедрении у конкретного заказчика, но не как система истины 1cAI.

Внутреннее ядро должно включать:

1. `Need -> Requirement -> Capability -> Architecture Element -> Work Item -> Code/Metadata -> Test Case -> Test Run -> Defect -> Release -> Incident`.
2. Requirements repository: ID, type, owner, rationale, source, acceptance criteria, priority, risk, status, version, baseline.
3. Traceability matrix: bidirectional links, orphan detection, coverage %, suspect links after upstream change.
4. Workflow engine: states, roles, validators, required fields/links, quorum approvals.
5. Change sets: пакет изменений с CR, diff, impact analysis, reviewers, decisions, merge into baseline.
6. Baselines/releases: immutable snapshots of requirements, architecture, tests and evidence.
7. Review packs: fixed artifact pack for review, comments, resolutions, approve/reject, audit trail.
8. Architecture repository: C4 + ArchiMate-lite + ADRs + generated diagrams from model.
9. Verification layer: test cases, automated result import, evidence, release readiness.
10. Open interchange: JSON/YAML/Markdown/CSV, ReqIF later, API/webhooks.

## Текущий 1cAI: сильные стороны

По текущему репозиторию и handoff у нас уже сильная основа:

1. Rentgen graph: SQLite-based graph/quality store, impact, flow, dead code, hotspots, reasons.
2. Change-driven analysis: change-impact, review-diff, standards/security/release readiness слои.
3. MCP and EDT-MCP bridge: статус, live tools, safe call, write/execute safety gate, approval records.
4. Requirements/traceability/governance modules: есть API и тесты, но их нужно собрать в единый ALM core.
5. Test inventory/coverage matrix: есть mapping на YAxUnit/Vanessa, но execution/evidence loop надо добить.
6. Offline/on-prem positioning: сильный ров; детерминированный анализ работает без LLM.
7. UI coverage: страницы под quality, change, requirements, testing, release readiness, security, metadata, operations, team governance, EDT-MCP.

## Текущий 1cAI: честные пробелы

| Gap | Риск | Что делать |
|---|---|---|
| Governance core пока рассыпан по модулям | Есть фичи, но нет одного "system of record" | Собрать Artifact Graph + Workflow + Baseline + Change Set API. |
| Policy engine не central product | Gates есть точечно, enterprise ждет единый policy-as-code | YAML/JSON policies, severity, waivers, owner approvals, status checks, evidence. |
| Test loop неполный | Affected tests есть, фактический прогон и evidence не гарантированы | YAxUnit/Vanessa/1C Test runner adapters, result persistence, flaky/history. |
| CI/CD не продуктовая упаковка | Пользователь должен собирать pipeline сам | Шаблоны GitHub/GitLab/Azure/Jenkins, artifacts, PR markdown, trend storage. |
| Enterprise IAM/audit слабее enterprise-нормы | JWT/RBAC недостаточно для больших компаний | OIDC/SAML, LDAP/SCIM, IdP groups, tenant isolation, audit/SIEM stream. |
| BA слой частично внешне-интеграционный | Риск зависимости от чужих продуктов | Делать внутренний repository; внешние sync только adapters. |
| DORA/evidence hygiene | В `docs/status/dora_history.md` есть conflict markers | Почистить evidence trail, сделать append-only metrics store. |
| Metadata ingestion not universal | Есть демо/снапшоты, но нужен вход любой конфигурации | EDT XML, Git, `.cf/.dt`, live DB, v8unpack adapters, incremental rebuild. |
| Form writer/import readiness | Blueprint есть, import-ready EDT XML writer еще в hardening | Реальный writer + visual diff + safe apply gate. |
| Productization/docs | Много мощных артефактов, но есть overclaims/encoding/placeholder | Единая maturity map, support matrix, deployment/security whitepaper. |

## Что продукт дает без подключенного AI

Это критично для продаж в закрытый контур. Без AI 1cAI должен работать как enterprise analyzer/governance platform:

1. Инвентаризация конфигурации: модули, методы, метаданные, связи, роли, формы, регистры, зависимости.
2. Impact analysis: что сломается при изменении функции/модуля/объекта.
3. Dead code и hotspot discovery: где техдолг и риск максимальны.
4. Standards/security/release gates: детерминированные правила, severity, fail/warn.
5. Test selection: какие YAxUnit/Vanessa/ручные тесты надо прогнать под конкретный change.
6. Traceability: требование -> объект 1C -> изменение -> тест -> релиз -> incident.
7. Approvals: кто разрешил рискованное действие, почему, на какой scope, когда использовано.
8. CI artifacts: markdown/json reports, exit codes, trend storage.
9. Dashboards для руководителей: readiness, risk, coverage, DORA/MTTR, blocked releases.
10. Audit/evidence pack: выгрузка для службы качества, архитекторов, ИБ и руководства.

AI тогда становится ускорителем: объясняет, генерирует план, предлагает код/тесты, чинит pipeline, но истина остается в графе, правилах и evidence.

## Product coverage map by roles

| Роль | Что нужно дать | Необходимые слои |
|---|---|---|
| Разработчик 1C | Быстро понять риск правки, получить diagnostics, тесты, diff review, безопасный apply | BSL LS, Rentgen impact, test selection, EDT-MCP, approval gate, CI report. |
| Архитектор | Видеть зависимости, подсистемы, данные, роли, интеграции, ADR, варианты решения | Architecture repository, C4/ArchiMate-lite, metadata graph, decision log. |
| BA/консультант | Вести требования внутри продукта, связывать с 1C-артефактами, получать acceptance scenarios | Requirements repository, traceability, review packs, baselines, test cases. |
| Руководитель разработки | Видеть загрузку рисков, readiness релиза, blockers, качество, DORA, tech debt | Executive dashboards, release gates, portfolio/app catalog, team governance. |
| QA | Понимать affected tests, запускать YAxUnit/Vanessa, хранить evidence, видеть gaps | Verification layer, test inventory, result import, defect links. |
| ИБ/compliance | Контроль risky patterns, privileged paths, secrets, approvals, audit | Security posture, policy engine, IAM, SIEM/audit stream. |
| Эксплуатация | Связать инцидент с кодом/релизом/метаданными, оценить rollback | Operations incident-to-code, release baseline, MTTR/DORA. |

## Приоритетная дорожная карта

### P0: собрать enterprise skeleton

1. **Artifact Graph / ALM Core**
   - Внутренние сущности: need, requirement, capability, architecture element, work item, change set, code/metadata object, test case, test run, defect, release, incident.
   - Links, versions, owners, statuses, comments, decisions.
   - API + UI "Repository", "Traceability", "Change Set".

2. **Policy & Gates Engine**
   - Policy-as-code: quality/security/test/release rules.
   - Severity, waivers, owner approvals, expiration, scope.
   - CI exit codes, PR/MR status check payload, markdown/json evidence.

3. **Test Execution & Evidence**
   - YAxUnit runner adapter.
   - Vanessa runner adapter.
   - Import JUnit/Allure/JSON results.
   - Store evidence, screenshots/logs links, flaky history.

4. **CI/CD Product Pack**
   - GitHub Actions, GitLab CI, Azure DevOps, Jenkins templates.
   - Self-hosted Windows runner profile for 1C.
   - Artifacts: risk report, traceability delta, test report, release gate report.

5. **BA Internal Core**
   - Requirements repository.
   - Review packs, baselines, suspect links.
   - External Jira/Confluence/ADO sync moved to optional adapters.

### P1: усилить 1C moat

1. **Canonical Metadata Model**
   - EDT XML, v8unpack JSON, live DB, `.cf/.dt`, extensions.
   - Objects, forms, commands, roles/RLS, registers, queries, scheduled jobs, exchanges.

2. **Official/community adapters**
   - BSL LS diagnostics/symbols.
   - 1C:АПК import.
   - Sonar import/export.
   - EDT CLI / Configurator batch wrappers.
   - OneScript/OPM task runner.

3. **Update and support assistant**
   - Типовая конфигурация update risk.
   - Compare/merge conflict explanation.
   - Direct modification vs extension recommendation.
   - Support status and vendor lock risk.

4. **Architecture Repository**
   - C4 + ArchiMate-lite.
   - ADRs.
   - Generated views from graph.
   - Validation in CI.

5. **Enterprise IAM/Audit**
   - OIDC/SAML, LDAP/SCIM, IdP group mapping.
   - Tenant/project boundaries.
   - Append-only audit, SIEM/Splunk/Datadog export.

### P2: agentic acceleration

1. Ask / Plan / Act / Review UX.
2. 1C-specific agents:
   - create metadata object;
   - review posting logic;
   - optimize query;
   - generate managed form blueprint;
   - generate YAxUnit/Vanessa tests;
   - prepare release/change pack;
   - analyze incident/log/TJ.
3. Rules/memory per project/team.
4. Local/offline LLM profile.
5. Marketplace of customer adapters: Jira, Confluence, ADO, Polarion, DOORS, TestRail, ServiceNow.

## Что не строить с нуля

1. Не переписывать BSL Language Server.
2. Не переписывать SonarQube.
3. Не переписывать Vanessa/YAxUnit.
4. Не заменять EDT и Конфигуратор.
5. Не делать Jira/Confluence/DOORS обязательной частью BA flow.
6. Не конкурировать с GitLab/GitHub как полноценной VCS/CI платформой.
7. Не обещать "полную автоматизацию разработки" без human approvals, test evidence и rollback path.

## Sources

### 1C official

- 1C:EDT: https://v8.1c.ru/platforma/1c-enterprise-development-tools/
- Configurator batch mode: https://v8.1c.ru/platforma/zapusk-konfiguratora-v-paketnom-rezhime/
- Group development / configuration repository: https://v8.1c.ru/platforma/gruppovaya-razrabotka/
- EDT + Git collaborative development: https://1c-dn.com/1c_enterprise/collaborative_development_with_git/
- EDT CLI scripts: https://edt.1c.ru/dev/ru/docs/plugins/dev/cli-script/
- EDT CLI plugin commands: https://edt.1c.ru/dev/ru/docs/plugins/dev/cli/
- 1C:Исполнитель: https://v8.1c.ru/platforma/1s-ispolnitel-dlya-administratorov/
- Configuration check: https://v8.1c.ru/platforma/proverka-konfiguracii/
- 1C:АПК: https://v8.1c.ru/tekhnologii/1s-avtomatizirovannaya-proverka-konfiguratsiy/
- Automated testing: https://1c-dn.com/1c_enterprise/automated_testing/
- 1C:Тестировщик: https://v8.1c.ru/tekhnologii/tekhnologii-krupnykh-vnedreniy/korporativnye-instrumenty/korporativnyy-instrumentalnyy-paket/1c-testirovshchik/
- Delivery and support: https://1c-dn.com/1c_enterprise/delivery_and_support/
- Extensions: https://v8.1c.ru/platforma/rasshireniya/
- ITS standards: https://its.1c.ru/db/v8std
- BSP: https://v8.1c.ru/tekhnologii/standartnye-biblioteki/1s-biblioteka-standartnykh-podsistem/
- SPPR: https://v8.1c.ru/tekhnologii/sistema-proektirovaniya-prikladnykh-resheniy/
- 1C:Управление ландшафтом: https://v8.1c.ru/tekhnologii/tekhnologii-krupnykh-vnedreniy/korporativnye-instrumenty/upravlenie-landshaftom/

### 1C community/open-source

- BSL Language Server: https://github.com/1c-syntax/bsl-language-server
- SonarQube BSL plugin: https://github.com/1c-syntax/sonar-bsl-plugin
- Vanessa Automation: https://github.com/Pr-Mex/vanessa-automation
- Vanessa ADD: https://github.com/vanessa-opensource/add
- YAxUnit: https://github.com/bia-technologies/yaxunit
- EDT Test Runner: https://github.com/bia-technologies/edt-test-runner
- OneScript: https://github.com/EvilBeaver/OneScript
- OPM: https://github.com/oscript-library/opm
- v8runner: https://github.com/oscript-library/v8runner
- gitsync: https://github.com/oscript-library/gitsync
- GitConverter: https://github.com/1C-Company/GitConverter
- EDT-MCP: https://github.com/DitriXNew/EDT-MCP

### AI copilots / agentic dev

- GitHub Copilot coding agent: https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent
- GitHub Copilot code review: https://docs.github.com/copilot/using-github-copilot/code-review/using-copilot-code-review
- GitLab Duo: https://docs.gitlab.com/user/gitlab_duo/
- GitLab Duo Agent Platform: https://docs.gitlab.com/user/duo_agent_platform/
- Sourcegraph Cody context: https://sourcegraph.com/blog/how-cody-provides-remote-repository-context
- Cursor Plan Mode: https://cursor.com/docs/agent/plan-mode
- Cursor Rules: https://cursor.com/docs/rules
- Cursor Cloud Agent: https://cursor.com/docs/cloud-agent
- Cursor security/privacy: https://cursor.com/security
- JetBrains Junie: https://www.jetbrains.com/help/ai-assistant/junie-agent.html
- Amazon Q Developer: https://aws.amazon.com/q/developer/
- SAP Joule for developers: https://www.sap.com/products/artificial-intelligence/joule-for-developers.html
- Power Apps Copilot: https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/ai-overview
- Copilot Studio: https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-what-is-copilot-studio
- ServiceNow App Engine: https://www.servicenow.com/products/now-platform-app-engine.html

### ALM / governance / testing

- Jira requirements management: https://support.atlassian.com/jira/kb/using-jira-for-requirements-management/
- Jira + Confluence: https://support.atlassian.com/confluence-cloud/docs/use-jira-and-confluence-together/
- Azure DevOps requirements: https://learn.microsoft.com/en-us/azure/devops/cross-service/manage-requirements
- Azure DevOps traceability: https://learn.microsoft.com/en-us/azure/devops/cross-service/end-to-end-traceability
- Polarion ALM: https://www.siemens.com/en-us/products/polarion/application-lifecycle-management-alm/
- IBM DOORS Next: https://www.ibm.com/docs/en/engineering-lifecycle-management-suite/doors-next/7.2.0?topic=overview-doors-next
- Sparx Enterprise Architect requirements: https://sparxsystems.com/enterprise_architect_user_guide/17.1/modeling_domains/requirementsmanagement.html
- ArchiMate overview: https://www.opengroup.org/archimate-forum/archimate-overview
- Structurizr DSL: https://docs.structurizr.com/dsl
- TestRail approvals: https://support.testrail.com/hc/en-us/articles/7766980011028-Test-case-review-approvals
- Xray requirement traceability: https://docs.getxray.app/space/XRAYCLOUD/44565208/Requirement%2BTraceability%2BReport

### Enterprise DevOps / quality / security

- GitHub self-hosted runners: https://docs.github.com/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners
- GitHub branch protection/status checks: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub audit log streaming: https://docs.github.com/en/enterprise-cloud@latest/admin/monitoring-activity-in-your-enterprise/streaming-the-audit-log-for-your-enterprise
- GitLab CI/CD: https://docs.gitlab.com/ci/
- GitLab security scanning: https://docs.gitlab.com/user/application_security/
- GitLab DORA metrics: https://docs.gitlab.com/user/analytics/dora_metrics/
- SonarQube quality gates: https://docs.sonarsource.com/sonarqube-server/latest/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates/
- Qodana quality gates: https://www.jetbrains.com/help/qodana/quality-gate.html
