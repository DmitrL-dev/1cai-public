# Backlog полного финального релиза

Дата исходной классификации: **16 октября 2026**, main после PR #104 `2d8254a`.
Частичный прогресс ниже актуализирован по интеграции PR #110, #112–#116
и завершению сохранённых блоков Git/Observer/уведомлений/three-way guards;
он не закрывает полные критерии реестра и не является новой публикацией.
Источник требований — [реестр 127 ID](FULL-FINAL-PLAN.md#реестр-127-требований);
этот документ не меняет их статусы и не закрывает ни одного критерия. Он фиксирует,
**чего не хватает** для каждой открытой строки, чтобы реализуемая часть шла в
обычный source+CI, а недостающее не выдавалось за готовность.

## Классы блокеров

| Класс | Чего не хватает | Что разблокирует |
| --- | --- | --- |
| `stand` | Лицензированный стенд 1С 8.3.27 / EDT 2026.1.3, собственные ИБ и хранилище | Доступ к стенду; native-gates исполняются на нём, обычный CI их не заменяет |
| `model` | Реальные запуски модели с бюджетом и независимой функциональной проверкой | Выделенный бюджет, выбранная модель и замороженный независимый набор задач |
| `human` | Участие людей: новый пользователь, клавиатура/доступность, независимый автор кейсов | Набор участников и протокол приёмки |
| `platform` | Целевая ОС/архитектура/железо вне Windows x64 и GNU/Linux x86_64 CI (macOS, arm64, minimum host, эталонное железо) | Решение о заявленных платформах и доступ к ним |
| `decision` | Решение владельца: архитектура оболочки/отладчика/AI, кто выдаёт approval, trust policy, роли, лицензия корпуса | Записанное решение (ADR), затем source+CI |
| `gated` | Выполнимо только после закрытия других gates | Закрытие перечисленных gates |
| `dev` | Только разработка в source+CI; ресурсов не хватает лишь по объёму очереди | Отдельный блок с тестами и CI |
| `pr84` | Отдельный draft #84 со своими gates | Решения и gates #84 |

`stand`/`model`/`human`/`platform`/`decision` не означают, что исходники пусты:
часть строк уже имеет код и обычные проверки. Строка закрывается только
полным критерием с квитанцией точного SHA.

## Реализовано в этом цикле

| ID | Что сделано | Что осталось |
| --- | --- | --- |
| `SNAP-DIFF-01` | [Exact-source CI `c2b6cd2`](evidence/development-ci-c2b6cd2-20261016.json): Linux pair, installed CLI/SDK, Windows regression | `platform`: minimum host, OS-wide airgap, macOS |
| `TEST-PROFILE-01`, `IDE-SC-20` (часть) | [TEST-RUN-QUAL-01](TEST-RUN-QUALIFICATION.md): повторная сверка retained YAxUnit artifacts в Core/CLI/Companion | `stand`: новые native pass/fail/crash/timeout/no-tests; `decision`: trusted executor attestation |
| `RELEASE-MILESTONE-01`, `RELEASE-DOC-SWEEP-01` (часть) | Один список допуска Core в Companion, проверка version claims, сборщик exact-commit CI evidence | Публикация milestone — действие владельца |
| `WORKFLOW-MIGRATION-01` (часть) | Контракты schema3→4: сохранность строк, откат на каждой границе, replay/conflict, отказы, подделка receipt; конкурентные state writers и Windows runner с читаемым/pinned backup, отказом на подмену | Полный crash/read-back критерий и точная поставочная приёмка остаются открытыми; source-тесты не подменяют её |
| `SNAP-PUB-01` (часть) | [Атрибуция точного locator](SNAPSHOT-PUBLICATION-ADR.md#read-only-generation-attribution-development-source) и [физическая проверка catalog-referenced поколения](SNAPSHOT-PUBLICATION-ADR.md#exact-generation-verification-development-source) через Core и Windows/Linux CLI; [реальный kill publisher](SNAPSHOT-PUBLICATION-ADR.md#abrupt-process-publication-recovery-development-source) на границах публикации, rollback/retry и точный replay после commit/later head, включая same-content reuse | Не определяется операция незарегистрированной попытки, её активность или состояние файлов; проверка зарегистрированного поколения не даёт cleanup lease. Lifecycle/exclusivity, kill внутри COMMIT/fsync, power-loss, полный критерий и установленная приёмка остаются открытыми |
| `GUI-IDE-BOUNDARY-01` | Статический guard: замыкание импортов GUI без IDE-модулей и закрытый набор read-only маршрутов | — |
| `PORT-GATE-01` (часть) | Раздел `components` в capability report; GUI проверяет его до чтения входов | `platform`: фактический отказ на macOS |
| `ANALYZER-01` (часть) | SARIF принимается только от заявленного анализатора и версии; unit-контракты BSL-LS проверяют unavailable/partial и точные source/candidate hashes | `decision`: Sonar/Vanessa; полная приёмка адаптеров остаётся отдельной |
| `OWNER-NOTIFY-01` (часть) | [Durable journal и явный foreground host](NOTIFICATION-DELIVERY.md) сохраняют backoff/unknown outcome, ограничивают циклы и восстанавливают принятый ack без resend; schema 2/3 factory связывает очередь с текущими правами и lifetime worker | `dev`: установленный SCM-сценарий доставки; `decision`: production endpoint/secret provisioning; source-контракты не подтверждают live endpoint, hard termination или power-loss |
| `IDE-SC-24` (часть) | Неизвестный исход [metadata](METADATA-LIVE-APPLY.md) и [BSL live-операции](PROPOSAL-LIVE-APPLY.md) сохраняет `live_source_written=null`; [platform CLI](PROPOSAL-PLATFORM-CHECK.md) заранее выдаёт recovery ID; обрыв до request в platform/test runs возвращает incomplete без слепого retry | `dev`: остальные долгие операции, lifecycle отмены и reconciliation; архивирование неполных runs требует отдельного доказательства отсутствия активного исполнителя; полный критерий открыт |
| `PORT-RETAINED-01` (часть) | [Linux retained metadata navigation и source reads для ручных drafts](PORTABLE-CORE.md) используют проверенные POSIX sessions с повторной авторизацией и ограниченными входами | `platform`: macOS; остальные retained-потребители и полный cross-OS lifetime/security scope остаются открытыми |
| `IDE-SC-08`, `IDE-SC-09`, `IDE-SC-17` (часть) | Preview rename сохраняет посторонние UUID/name; BSL Problems указывают закреплённый analyzer profile без автоматических правок; синтетические preview/merge/workspace проверки сохраняют binary bytes | Полные IDE-сценарии переименования/диагностики и native MXL-печать остаются открытыми |
| `SNAP-OBS-02` (часть) | [Observer](OBSERVER.md) сохраняет пропуски и регрессии часов для CLI и capture-службы schema 1/3, включая перезапуск; kill-тесты покрывают открытые транзакции polling/report/findings | Kill во время самого COMMIT/fsync и полный lifecycle не квалифицированы; schema 2 без capture использует отдельный scheduler journal |
| `GIT-WATCH-01` (часть) | [Git tree binding](GIT-SNAPSHOT-EVIDENCE.md) сверяет captured bytes с regular blobs точного commit; included untracked/filter-transformed bytes отказывают, legacy evidence сохраняет прежний scope | Полнота всего repository tree и временная атомарность не доказаны; production qualification отдельная |
| `OWNER-STORE-01` (часть) | [Явная max-age policy](OWNER-REPORT-STORE.md) добавляет historical/freshness в read view библиотеки и Windows CLI/MCP, не меняя retained receipt | Полная установленная cross-platform приёмка остаётся открытой; новый выпуск и актуальность данных работающей 1С этим блоком не подтверждены |
| `UPDATE-SEMANTICS-01` (часть) | [Three-way guards](METADATA-THREE-WAY.md) запрещают UUID/type replacement, чужие owner namespaces и неизвестные XML/HTML Ext resources, включая unchanged; бинарные ресурсы сохраняют атомарные path-based правила | Поддержка остальных семантических scopes и native Designer/EDT приёмка остаются открытыми |

## Строки, требующие стенда 1С/EDT (`stand`)

`IDE-SC-01`, `IDE-SC-02`, `IDE-SC-03`, `IDE-SC-04`, `IDE-SC-05`, `IDE-SC-10`,
`IDE-SC-13`, `IDE-SC-14`, `IDE-SC-15`, `IDE-SC-16`, `IDE-SC-18`, `IDE-SC-19`,
`IDE-SC-21`, `IDE-GATE-01`, `IDE-VERSION-01`, `FINAL-NATIVE-01`, `FINAL-EDT-01`,
`FINAL-UPDATES-01`, `ROADMAP-06`, `NATIVE-FIXTURE-01`, `NATIVE-EXTEND-01`,
`EDT-PLAN-01`, `EDT-PLAN-02`, `EDT-DESIGN-01`, `CONFIG-MATRIX-01`,
`META-BUSINESS-01`, `EDT-PROFILE-01`, `EDT-COMMAND-01`, `SERVICE-NATIVE-01`,
`TEST-YAXUNIT-01`, `IDE-BACKEND-01`, `IDE-COVERAGE-01`, `PLATFORM-FINAL-01`,
`DIAG-NATIVE-01`, `DIAG-SOURCE-RUNTIME-01`, `OWNER-RUNTIME-01`.

Подготовка без стенда (fixtures, orchestration, отказ без платформы) допустима,
но ни одна из этих строк не закрывается обычным CI.

## Строки, требующие модели, людей или платформы

| ID | Класс | Чего не хватает |
| --- | --- | --- |
| `FINAL-AI-01`, `ROADMAP-02`, `DAILY-SEMANTIC-01`, `DAILY-RED-01` | `model` | Новый семантически верный результат модели с независимой проверкой; отрицательные записи сохраняются |
| `DAILY-NATIVE-01`, `DAILY-FROZEN-01` | `stand` + `model` | Реальный editor/model/1С сценарий; контракт frozen inputs уже есть |
| `IDE-AI-01`, `PERF-LOCAL-01`, `FINAL-DIAG-01`, `DIAG-INDEPENDENT-01`, `DIAG-DELIVERY-01` | `model` + `human` + `decision` | Сравнение ready-agent/Rust/hybrid на независимом holdout; план ставит host/delivery после A/B |
| `REPAIR-CONTRACT-01`, `EDITOR-REPAIR-01` | `model` + `human` | Положительный реальный repair; контракт парсера и recovery уже проверяются |
| `FINAL-ONBOARD-01`, `ROADMAP-01` | `human` | Замер первого результата нового пользователя и восстановления |
| `IDE-SC-23` | `human` + `model` | Solo/team и agent-off/on на настоящих людях и агенте |
| `FINAL-GUI-01`, `IDE-OS-01`, `IDE-SC-22`, `FINAL-DELIVERY-MATRIX-01` | `platform` + `human` | macOS/arm64 маршруты и GUI-приёмка; lifecycle-верификаторы Windows/Linux — `dev` |
| `EDITOR-CURRENT-01` | `gated` | Квитанция editor workbench на точных bytes milestone |
| `FINAL-PERF-01`, `ROADMAP-04` | `platform` + `decision` | Представительный корпус (лицензия) и эталонное железо; harness — `dev` |

## Строки, требующие решения владельца (`decision`)

| ID | Решение |
| --- | --- |
| `WORKFLOW-APPLY-01`, `META-GATE-01`, `META-LIVE-01` | **Security-relevant.** Кто выдаёт одноразовый approval live-записи (человек/агент) и schema 5 runs/approvals/effects. Сейчас live-записи доступны MCP-клиенту по умолчанию с `destructiveHint` и полагаются на approval клиента; `--allow-tool` сужает процесс, но не другие процессы того же OS-аккаунта |
| `WORKFLOW-DURABLE-01` | Schema 5 durable runs и profile revisions (часть ADR) — вместе с решением выше |
| `IDE-PERMISSION-01` | Модель ролей agent/manual и общая очередь операций |
| `IDE-SHELL-01`, `IDE-SC-11`, `IDE-SC-12`, `IDE-STATE-02` | Выбор оболочки (Theia/Companion) и DAP backend |
| `GIT-PRODUCTION-01`, `GIT-TRUST-01`, `SNAP-OBS-01`, `OBSERVER-SERVICE-01`, `SERVICE-INSTALL-01` | Production trust/ACL policy, подпись и native launcher службы |
| `FINAL-SPECTORN-01` | Включается ли защищённый маршрут Spectorn в продукт |
| `PORT-IDENTITY-01` | Политика явной передачи identity между машинами |
| `IDE-INDEX-01`, `IDE-SC-06`, `IDE-SC-07` | Представительный корпус и принятие BSL-LS как индекса; incremental index — `dev` |

## Отдельные зависимости (`pr84`, `gated`)

- `FINAL-SOURCE-01` — PR #84 остаётся draft; его lifecycle/full176/whole-process,
  source cohort и installed gates не обходятся.
- `FINAL-STABLE-CHANNEL-01` — по критерию реализуется после полной готовности;
  сейчас `verify_release_plan` намеренно не достигает stable.
- `FINAL-IDE-01` — после всех 24 IDE-сценариев.

## Очередь разработки (`dev`)

Реализуемо в source+обычном CI без недостающих ресурсов, но не вошло в этот цикл:
`SNAP-READ-01` (Windows suite
read sessions),
`RUST-DELIVERY-01` (квитанция текущего HEAD), `UPDATE-3WAY-01`,
`UPDATE-BSL-01`, `EDT-IDENTITY-01`, `META-WORKSPACE-01`,
`OWNER-REPORT-01`, `ROADMAP-03`,
`ROADMAP-05`, `ROADMAP-07`, `FINAL-PORTABLE-01`, `DIAG-CONTEXT-01`,
`DIAG-RECEIVER-01`, `DIAG-HOST-01`, `DIAG-PROTOCOL-01`, `DIAG-REVISION-01`,
`DIAG-CHECK-01`, `DIAG-CONTROLS-01`, `DIAG-FAIRNESS-01`, `RELEASE-POLICY-01`,
`IDE-STATE-01`. Benchmark harness для замеров тоже здесь: он требует
изменения workflow с проверкой `actionlint`.

## Закрытые компонентные записи

`COMPONENT-CI-19`, `COMPONENT-WIN-19`, `COMPONENT-LINUX-19`,
`COMPONENT-PUBLIC-19` и `HIST-NATIVE-20260915` сохраняют свой точный scope и не
переносятся на новые сборки.
