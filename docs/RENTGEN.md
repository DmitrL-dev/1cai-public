# 1С:Рентген — рентген конфигурации 1С

> **Не ещё один копайлот для 1С, а рентген, который показывает: что сломается, что мертво и что рискованно во всей конфигурации — объяснимо и без отправки кода в LLM.**

## Зачем это нужно

Рынок AI-инструментов для 1С сходится на «LLM + MCP-контекст» для **генерации** кода: 1С:Напарник (официальный, в EDT), GigaCode (BSL пока не поддерживает), Cursor/Claude-правила. Статический анализ держат BSL Language Server (180 диагностик) и SonarQube — но **пофайлово**, без анализа всей конфигурации.

Никто из заметных игроков **не владеет аналитическим слоем**: граф вызовов всей конфигурации, impact-анализ («что я сломаю»), мёртвый код по всему графу, объяснимый риск-рейтинг. Это структурно проверяемо (граф — это факты, а не вероятности) и закрывает реальные боли: регрессии при правках огромных типовых (ERP/УХ), ревью «в масштабе», онбординг в легаси.

1С:Рентген занимает именно эту нишу — **token-free** (анализ без обращения к LLM, код не покидает контур).

## Что умеет (проверено на реальной 1С:ERP УХ)

Граф: **26 748** оценённых модулей · **730 416** подпрограмм · **1 477 681** ребро вызовов.

| Возможность | Эндпойнт | Страница |
|---|---|---|
| **Очаги риска** — объяснимый рейтинг модулей: поддерживаемость × сложность × антипаттерны × радиус поражения (fan-in). Каждый очаг раскрывается до конкретных причин. | `GET /api/v1/quality/hotspots` | `/quality` |
| **Impact / blast radius** — обратный граф: кто зависит от функции (что сломается при правке) | `POST /api/v1/rentgen/impact` | `/rentgen` |
| **Execution flow** — прямой граф: что вызывает точка входа | `POST /api/v1/rentgen/flow` | `/rentgen` |
| **Мёртвый код** — экспортные функции общих модулей без входящих вызовов | `GET /api/v1/rentgen/dead-code` | `/quality` |
| **Качество модуля** — сложность/документация/поддерживаемость + флаги антипаттернов | `GET /api/v1/quality/{module,worst,search,summary}` | `/quality` |
| **Окрестность модуля** — кто вызывает / кого вызывает (срез графа) | `GET /api/v1/rentgen/module-neighbors` | — |

## Архитектура (без Neo4j и Docker)

```
.bsl (1С:ERP)
  └─ Go bsl-scan  ──►  data/rentgen_callgraph.ndjson   (730K функций, граф вызовов)
  └─ bsl_scoring  ──►  gabriel_runs/scores.json         (26 748 модулей, оценки)
                              │
            tools/rentgen/build_store.py  (3-уровневое разрешение вызовов, ~30с)
                              ▼
                      data/rentgen.db  (SQLite — единственное хранилище)
                              │
            tools/rentgen/store.py  ──►  FastAPI (/quality, /rentgen)  ──►  React-портал
```

Граф вызовов и оценки живут в одном самодостаточном SQLite-файле и отдаются in-process. Никаких внешних сервисов — это и решение под отсутствие Docker на хосте, и продуктовое позиционирование (data sovereignty).

## Запуск

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_rentgen.ps1
```
Скрипт собирает `data/rentgen.db` при первом запуске (~30с), поднимает бэкенд (:8000) и портал (:3000, либо ближайший свободный порт вроде :3001).

- Рабочий пульт и demo story: <http://localhost:3000>
- Pre-flight конфигурации EDT/Git/XML: <http://localhost:3000/configurations>
- Platform Doctor: <http://localhost:3000/platform-doctor>
- Lock Radar: <http://localhost:3000/lock-radar>
- Extension Safety: <http://localhost:3000/extension-safety>
- Update War Room: <http://localhost:3000/update-war-room>
- Rights/RLS: <http://localhost:3000/rights-rls>
- Value Packs: <http://localhost:3000/value-packs>
- Business Case: <http://localhost:3000/business-case>
- Productization: <http://localhost:3000/productization>
- Evidence Bundle: <http://localhost:3000/evidence-bundle>
- Vendor Portfolio: <http://localhost:3000/vendor-portfolio>
- Очаги риска: <http://localhost:3000/quality>
- Граф вызовов: <http://localhost:3000/rentgen>
- API-доки: <http://127.0.0.1:8000/docs>
- Вход в dev: кнопка «Dev Mode» на экране логина. Она получает настоящий JWT через demo user
  `admin/admin123`, а не кладет фиктивный токен в localStorage.

## Demo path и Query Surgeon

Главная страница показывает complete demo story: ERP-заказ, риск LEFT JOIN без `ЕстьNULL`, blast radius,
тест-план, go/no-go для релиза и markdown-отчеты для разработчика, архитектора, директора, QA,
эксплуатации и вендора. API: `GET /api/v1/management/demo`, `GET /api/v1/management/role-report/{role}`.

Pre-flight wizard `POST /api/v1/management/intake/plan` проверяет локальный EDT/Git/XML источник без
мутаций: считает BSL/XML/Form/Rights/Test файлы, показывает coverage/caveats и следующие действия.

Fallback standards review теперь содержит 1С-правило `join-field-null-guard`: поля из левого соединения
должны быть защищены через `ЕстьNULL(...)`, явную проверку `ЕСТЬ NULL` или замену на внутреннее
соединение, если отсутствие связанной строки невозможно по бизнес-правилу.

## Platform Doctor v1

`GET /api/v1/platform-doctor/analyze` и страница `/platform-doctor` собирают локальный inventory:
версия платформы, целевая версия, режим совместимости, СУБД, кластер/режим инфобазы, техжурнал,
OpenMetrics, события лицензирования и расширения. V1 не делает сетевых probe и не выдумывает
безопасность: неизвестные факты становятся warning/checklist.

Полезные env-поля для стенда:

- `ONEC_PLATFORM_VERSION`
- `ONEC_TARGET_PLATFORM_VERSION`
- `ONEC_COMPATIBILITY_MODE`
- `ONEC_DBMS`
- `ONEC_CLUSTER` / `ONEC_INFOBASE_MODE`
- `ONEC_TECH_JOURNAL_PATH`
- `ONEC_OPENMETRICS_URL`
- `ONEC_LICENSE_EVENTS_PATH`

## Lock Radar v1

`POST /api/v1/lock-radar/analyze` и страница `/lock-radar` разбирают локальный технологический журнал по
операционным событиям `TLOCK`, `TTIMEOUT` и `TDEADLOCK`. Отчет показывает decision/risk score, цепочки
событий, пользователей/процессы, затронутые модули, impact через `data/rentgen.db`, test gaps, actions и
runbook. Если путь к ТЖ не передан или срез пустой, это явно остается caveat, а не тихий зеленый ноль.

## Extension Safety v1

`POST /api/v1/extension-safety/analyze` и страница `/extension-safety` проверяют локальные CFE/EDT-расширения:
inventory, BSL/XML/rights-файлы, заимствованные объекты, привилегированный режим, явные транзакции, write hooks,
фоновые задания, risky query-сигналы, impact по графу и test gaps. V1 не обещает семантический merge как EDT,
но превращает расширения в отдельный release-gate и evidence-артефакт.

## Vendor Portfolio v1

`GET /api/v1/vendor-portfolio/audit` и страница `/vendor-portfolio` собирают pre-sale audit pack
для вендора/франчайзи: executive score, риск конфигурации, готовность подключения EDT/Git/XML,
Platform Doctor, top risks, work packages и markdown для КП/письма клиенту. V1 честно ограничен
одной текущей конфигурацией и не выдает коммерческие оценки как фиксированное обязательство.

`POST /api/v1/vendor-portfolio/portfolio` добавляет portfolio mode: несколько клиентов/путей превращаются
в агрегированный pipeline с average score, ready/watch/risk counts, opportunity work packages и markdown.

## Value Packs Center v1

`GET /api/v1/value-packs/catalog` и страница `/value-packs` превращают набор возможностей в
покупаемые пакеты: Developer, Architect, Release/QA, Platform Doctor/Lock Radar/Extension Safety, Vendor Portfolio и Enterprise
Offline. Каждый пакет содержит audience, outcome, deliverables, proof points, route links, maturity и
licensing story: локальный анализ и evidence не завязаны на обязательный расход токенов.

## Business Case v1

`POST /api/v1/business-case/build` и страница `/business-case` собирают директорский deal-room report:
first-year visible value, displacement обязательной AI-подписки, ручное review effort, release queue/risk exposure,
buyer committee, objections, offer stack и 30/60/90 rollout. Отчет не обещает гарантированную экономию:
все денежные рычаги строятся из явных assumptions и локальных Rentgen evidence.

Business Case now also includes `subscription_escape_plan`: three-year AI-rent baseline, local-license anchor,
break-even months, stakeholder lines and guardrails that keep core value separate from optional AI credits.

Fast health endpoints for `/business-case`, `/vendor-portfolio`, `/value-packs` and `/enterprise-trust-center`
now use the shared buyer pulse instead of deep report builders. Dashboards get instant `purchase_status`,
three-year AI-rent and source fields; full proof remains behind explicit build/audit/catalog actions.

## Productization Console v1

Страница `/productization` выводит enterprise delivery console поверх `/api/v1/productization`:
readiness score, deliverables/findings, SBOM generation, offline manifest, ZIP archive, delivery passport and verification.
Подпись manifest/archive остается env-based через `ONECAI_BUNDLE_SIGNING_KEY`; секреты не передаются через UI/API body.
ZIP archive contains `DELIVERY_PASSPORT.json` and `DELIVERY_PASSPORT.md` with signature policy, verification commands,
acceptance gates and role handoff for developer/QA, architect/security and director.

## Governance Center UI

`/approvals` shows local EDT-MCP approval records with status filters, scoped create flow, approve/reject
actions, linked records and argument constraints. `/audit` shows hash-chain verification, recent audit events,
broken entries if any, and JSONL/JSON export. These pages make approval/audit proof visible before the same
evidence is packed into Evidence Bundle.

## Commercial Offer Close Packet

`/commercial-offer-studio` now includes a `close_packet`: primary paid ask, one-page order, mutual action
plan, buyer commitments, proof requirements and checkout gates through `/approvals`, `/audit` and
`/evidence-bundle`. If trust/productization is risky, the ask becomes paid hardening before rollout instead
of pretending the enterprise license is safe to sell.

## Killer Demo Commercial Close

`/killer-demo` now projects the same commercial close packet into the buyer-ready demo route. The report
shows close readiness, checkout gates, approval/audit/evidence requirements and the one-page paid ask next
to Deal Readiness, so the presenter can end with a purchase, paid proof sprint, pilot or hardening motion.

## Board Pack Close Packet

`/board-pack` now carries a `board_close_packet`: the director-facing paid ask, one-page order, approval/audit
checkout gates, buyer commitments, evidence requirements and close script. Its proof packet includes
Governance Proof and Audit routes, so the board artifact can move to procurement without losing trust proof.

## Pilot Activation Contract

`/pilot-launchpad` now includes an `activation_contract`: selected paid offer, primary ask, invoice trigger,
Day 0/7/30 milestones, buyer commitments and approval/audit/evidence gates. It turns a signed interest into
a concrete paid start with owner, date, proof recipient and governance routes.

## Outcome Governance Refresh

`/outcome-ledger` now includes `governance_refresh`: approval, audit, Evidence Bundle and trust gates for
Day 7/30/60/90 proof refresh. Outcome proof now carries Governance Proof and Audit routes into rollout,
renewal, expansion or hardening decisions.

## Launch Room Buyer Journey

`/launch-room` now connects the buyer path as Close -> Activate -> Govern -> Realize. The cockpit shows
board checkout gates, paid pilot activation gates, governance proof gates and the next route when something
is not ready. `/approvals` and `/audit` are part of the proof packet, so procurement and security can verify
who approved the action and whether the audit chain is intact before the buyer receives final artifacts.

## Evidence Bundle v1

`POST /api/v1/evidence-bundle/build` и страница `/evidence-bundle` собирают единый переносимый
пакет доказательств: Platform Doctor, Configuration Intake, Demo Story, Value Packs, Vendor Portfolio,
Update War Room, опциональные Lock Radar по ТЖ и Extension Safety по расширениям, Rights/RLS. Каждый артефакт возвращается как JSON/Markdown с SHA-256, а общий
manifest можно приложить к approval, КП или внутреннему аудиту. V1 также отдает unsigned ZIP proof archive
через `/api/v1/evidence-bundle/archive`; подписанный offline bundle остается зоной Productization.
Governance proof добавляет `governance-proof.json/.md`: approval records, Safe Autopilot linkage,
audit-chain verification and recent audit events travel inside the same archive.
The Audit page and API also expose SIEM-ready handoff through `/api/v1/audit/siem-export`: normalized
JSONL/JSON events with chain-valid context and export SHA-256, while live SIEM streaming remains adapter work.

## Update War Room v1

`POST /api/v1/update-war-room/plan` и страница `/update-war-room` отвечают на вопрос “можно ли
обновлять”: источник конфигурации, целевая платформа, Platform Doctor, расширения, impact релиза,
affected tests, rollback/evidence и workstreams для архитектора, эксплуатации, релиза и директора.
Если change set или `data/rentgen.db` не доступны, это явно выводится как caveat, а не как зелёный
статус.

## Rights & RLS Simulator v1

`GET /api/v1/rights-rls/analyze` и страница `/rights-rls` строят локальную матрицу
роль → объект → действие по `Roles/*/Ext/Rights.xml`, показывают dangerous rights
(`Delete`, `Update`, `Administration` и близкие), консервативно фиксируют RLS/condition
сигналы и дают security gate для релиза. V1 не утверждает runtime-доступы: параметры сеанса,
привилегированный код и whitelist admin/service ролей остаются отдельными проверками.

Ручная сборка хранилища: `C:\Python311\python.exe tools\rentgen\build_store.py`.

## Что факт, что эвристика

Чёткая граница между проверяемыми фактами и непроверенной эвристикой (API отдаёт те же
оговорки в полях `risk_basis`/`risk_caveat`/`code_quality_basis`):

| Сигнал | Статус | Оговорка |
|---|---|---|
| Граф вызовов (`flow`) | **факт** | только квалифицированные `Модуль.Функция` + локальные вызовы; динамический `Выполнить()` и неквалифицированные глобальные вызовы → возможны ложные отрицания (пропуск ребра) |
| Impact / blast radius (`impact`, `change-impact`) | **факт** | измеряется по графу; формы (~44% модулей) в граф не попадают → их impact **не измерен**, а не «ноль» (`impact_measured=false`) |
| Мёртвый код общих модулей (`dead-code` scope=common) | **факт** | только экспортные функции общих модулей; не учитывает рефлексию и вызовы из других конфигураций — **проверяйте перед удалением** |
| **Риск-рейтинг** (`hotspots`, `risk` в ответах) | **эвристика (непроверенная)** | `risk = поддерживаемость×сложность×антипаттерны × blast(fan-in)`, веса 0.40/0.25/0.10 подобраны экспертно, cap 25, blast 0.65–1.0. **Бэктеста против размеченных дефектов нет** — это объяснимая приоритизация, а не вероятность дефекта. `risk_basis="explainable_heuristic"`. |
| `maintainability_score` | формульная оценка | в пакетном прогоне считалась с `fan_in/fan_out=0` (формула поддерживает реальные значения, но прогон их не подал) — учитывайте при чтении риска, куда она входит ведущим весом |
| `code_quality` (GBR) | **деприкейт / некалибровано** | ML-модель статистически бесполезна (CV R²≈−0.06 на 611 примерах), **ничего не ранжирует**, в ответе помечена `code_quality_basis="deprecated_uncalibrated"`; при отсутствии предсказания не выдаётся как настоящее число |

Коротко: **граф / impact / blast-radius / мёртвый код общих модулей — структурные факты** (с раскрытыми
пробелами по динамическим вызовам и формам). **Риск-рейтинг — непроверенная объяснимая эвристика.**
GBR-`code_quality` де-факто выключен из принятия решений.

## Методология и честные оговорки

Аналитический инструмент полезен ровно настолько, насколько ему доверяют. Поэтому:

- **Риск — прозрачная формула, не чёрный ящик.** `risk = quality_risk × blast` где `quality_risk = 0.40·(100−поддерживаемость) + 0.25·сложность + 0.10·(100−документация) + штрафы за антипаттерны (≤25)`, а `blast = 0.65…1.0` от fan-in (централизованность в графе). Каждый очаг отдаёт `reasons[]` с вкладом каждого фактора.
- **Разрешение вызовов — точность важнее полноты.** Учитываются только квалифицированные `Модуль.Функция` и локальные вызовы внутри модуля. «Резолвинг по имени» отключён (отброшено ~3.37M неоднозначных рёбер, включая обращения к платформенным методам `Вставить/Добавить/Количество`). Следствие: возможны **ложные отрицания** (пропуск ребра при динамическом `Выполнить()` или вызове глобального общего модуля без квалификации), но **ложные срабатывания минимизированы** — граф можно показывать как факт.
- **Мёртвый код — только общие модули.** Экспортные функции объектных/менеджерских/форм модулей вызывает платформа (обработчики событий, команды, веб-методы) без BSL-ребра, поэтому они исключены. Не учитываются `Выполнить()`/рефлексия и вызовы из других конфигураций — **проверяйте перед удалением**.
- **GBR-оценка `code_quality` намеренно не выпячивается.** Обученная модель статистически слаба (CV R² ≈ −0.06 на 611 размеченных примерах). Ведущий сигнал — формульные оценки + объяснимый риск, а не ML-число.

## Данные и тесты

- Источники: `data/rentgen_callgraph.ndjson` (503 МБ), `gabriel_runs/scores.json` (26 748 модулей).
- Хранилище: `data/rentgen.db` (~365 МБ, пересобираемо).
- Тесты движка: `tests/unit/test_rentgen_store.py` — `C:\Python311\python.exe -m pytest tests/unit/test_rentgen_store.py -q` (10/10).

## Что дальше (бэклог)

- Переход с очагов на drill-down модуля: клик по очагу → деталь с окрестностью графа (`module-neighbors`).
- Интеграция BSL Language Server (180 диагностик) для замены формульных флагов реальными диагностиками в «причинах риска».
- Экспозиция аналитики через MCP — быть аналитическим бэкендом для Cursor/Claude/Напарника, а не конкурировать за редактор.
- Пересчёт `maintainability` с реальным fan-in/fan-out (формула это поддерживает; пакетный прогон считал с нулями).
