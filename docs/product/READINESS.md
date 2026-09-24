# Состояние публичной поставки — 24 сентября 2026

Актуальная [карта рынка и выбранное направление](COMPETITOR-MATRIX.md)
поясняют, какие соседние инструменты мы интегрируем и какие незакрытые
сценарии остаются нашим преимуществом.

[Матрица совместимости и evidence](CONFIGURATION-COMPATIBILITY.md) отделяет
синтетический EDT read-only contract от исторических native экспериментов;
добавление corpus не квалифицирует типовые `.cf/.cfe` и live apply.

## Выпуск 24 сентября 2026 — core dev11 и Companion 0.1.11

Текущая пара раннего доступа: [core `0.1.0.dev11`](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev11)
и [Companion `0.1.11`](https://github.com/DmitrL-dev/1cai-public/releases/tag/companion-v0.1.11).
Core исправляет запись полных Windows file ID в запечатанном архиве нативных
запусков: большие значения сохраняются без потери старших битов, а повторная
проверка отклоняет подмену файла. [Манифест](../../releases/core/0.1.0.dev11/manifest.json)
привязывает принятый push-CI ZIP к исходному коммиту `441e838` и SHA256
`9351d2b8790a358f66931a3067e8ba1823b61b7ca6b97989bb430f8fd124441a`.
Офлайн-проверка принятого ZIP подтвердила 40 файлов, 30 зафиксированных wheels
и 32 MCP-инструмента. [Push](https://github.com/DmitrL-dev/1cai-public/actions/runs/35949352582),
[PR](https://github.com/DmitrL-dev/1cai-public/actions/runs/35949391693)
и [CI объединённого main](https://github.com/DmitrL-dev/1cai-public/actions/runs/35955558552)
завершились успешно; JUnit каждого из этих прогонов содержит 2331 Python-тест
без ошибок и пропусков. Node, Go, сборка комплекта и установленные проверки
тоже прошли.

VSIX Companion размером 208753 байта имеет SHA256
`916e1311a5bd8ea43c05e7220c547239bb056a963b85ab7746a13ff8e67f83d5`.
[Релизный workflow](https://github.com/DmitrL-dev/1cai-public/actions/runs/35958567239)
повторно собрал расширение, сверил хэш и размер с манифестом, проверил
скачанный артефакт и создал черновик. После отдельной сверки трёх файлов
черновик опубликован как prerelease. Профиль выбирает
установленный core dev11 явно; старые профили не переписываются.

После подготовки релиза установленный **принятый CI ZIP** прошёл
[ограниченный нативный сценарий BSL apply/Undo](PROPOSAL-LIVE-APPLY.md#installed-dev11-follow-up-on-native-1c)
в отдельной собственной файловой базе 1С 8.3.27.2342. Все 11 нативных шагов
завершились с кодом 0; приложение вернуло 43 после применения и 42 после Undo.
Полный inventory шести исходных файлов восстановлен по хэшам, UUID сохранены,
модель не вызывалась. [Машинная квитанция](evidence/proposal-live-native-dev11-20260924.json)
связывает публичный ZIP, установленный wheel, платформу и результаты. Полный
dump платформы побайтно не совпадает из-за `ConfigDumpInfo.xml`; это не
заявляется как полная нативная приёмка.

После публикации этой пары [Companion 0.1.11 с установленным core dev11](EDITOR-TESTS.md#опубликованные-companion-0111-и-core-dev11--24-сентября-2026)
прошли отдельный сценарий в extension host: выбрана ревизия 1 при актуальной
ревизии 2, baseline дал один ожидаемый failure, candidate — один passed в
отдельной файловой базе 1С/YAxUnit. Второй процесс редактора после отключения
профиля прочитал прежний отчёт без нового запуска. Исходный модуль и head
сохранились, модель не вызывалась. [Квитанция](evidence/tests-editor-dev11-20260924.json)
связывает публичный VSIX, установленный core, платформу и локальные отчёты;
runtime VS Code целиком не закреплён и не аттестован извне.
Позднейший [повтор на новом проекте](EDITOR-RUNTIME-PIN-DEV11.md) подтвердил
совпадение состава, размеров и SHA256 всех 2473 файлов локальной установки
VS Code в снимках до первого и после второго процесса редактора; системная
среда и внешний хост этим не аттестованы.

Установленный Core dev11 дополнительно прошёл
[нативный консольный прогон Source Observer](SERVICE-CONSOLE-NATIVE-DEV11.md)
на новом собственном BSL-проекте: первый процесс создал один report, повторный
не создал дубликат, а чужой project ID получил ограниченный отказ. Проверка
сверила 92 файла установленного пакета с wheel релиза и сохранила
[квитанцию](evidence/service-console-native-dev11-20260924.json).
Windows SCM при этом не использовался.

Следующий [локальный нативный прогон GitAuditWorker](SERVICE-GIT-NATIVE-DEV11.md)
с настоящим BSL-LS подтвердил `analyzed`/`unchanged` и два finding на новом
коммите с пустым обработчиком. Одновременно первый цикл на новых каталогах
runtime отказал с `BSL_INPUT_CHANGED` без успешного owner report; паузы 5 и
30 секунд на отдельных свежих runtime не устранили отказ. Позднейшие
контрольные вызовы самого native-адаптера после новых установок, включая серию
3/3 первых успешных анализов, не воспроизвели его. Они не заменяют первый цикл
GitAuditWorker и не устанавливают причину расхождения. [Ограниченная квитанция](evidence/service-git-native-dev11-20260924.json)
и [issue #23](https://github.com/DmitrL-dev/1cai-public/issues/23) фиксируют
обе стороны наблюдения и незакрытую приёмку свежей установки.

Позднейшая [повторная проверка полного worker на двух новых runtime](SERVICE-GIT-COLD-RECHECK-DEV11.md)
25 сентября дала первые `analyzed` для schema 3 и schema 2, а затем циклы без
повторного `analyzed`. Оба runtime и профиля были новыми, но проект и snapshot —
уже существовавшими на том же Windows-хосте. [Ограниченная квитанция](evidence/service-git-cold-recheck-dev11-20260925.json)
связывает входные хэши, outbox и журнал. Эти два успеха показывают
непостоянство прежнего отказа полного цикла; причина `BSL_INPUT_CHANGED`
по-прежнему неизвестна, issue #23 и холодная приёмка остаются открытыми.

[Проверка девяти новых регистраций проекта](SERVICE-GIT-NEW-PROJECT-DEV11.md)
25 сентября обнаружила ещё один первый отказ полного schema 2 worker: публичный
CLI вернул `SERVICE_WORKER_FAILED`, журнал `GIT_ANALYZER_INCOMPLETE`, outbox
`fatal` без owner report. Повтор того же runtime дал `analyzed`; шесть других
проектов с диагностическим hook и два проекта через обычный CLI прошли первые
циклы с настоящим `bsl/MagicNumber` finding. [Новая ограниченная квитанция](evidence/service-git-new-project-dev11-20260925.json)
разделяет эти входы и результаты. Внутренняя причина именно нового отказа не
записана, поэтому его нельзя автоматически назвать `BSL_INPUT_CHANGED`.
Холодная приёмка и issue #23 остаются открытыми.

Отдельный [нативный прогон schema 3](SERVICE-GIT-SCHEMA3-NATIVE-DEV11.md)
на уже использованном runtime подтвердил автономный захват нового snapshot
после Git-коммита, `git_source_verified` owner report и второй цикл без новой
записи outbox. Это один синтетический модуль в console mode; холодный runtime
и Windows SCM он не квалифицирует. [Квитанция schema 3](evidence/service-git-schema3-native-dev11-20260924.json)
связывает установленный dev11 с commit, snapshot и исходным модулем.

Базовый публичный `main` перед этой синхронизацией checkpoint —
[`325e9892350ac5ae0b1ccf9dee4f16b80edfd715`](https://github.com/DmitrL-dev/1cai-public/commit/325e9892350ac5ae0b1ccf9dee4f16b80edfd715).
[Postmerge Windows CI](https://github.com/DmitrL-dev/1cai-public/actions/runs/36005364585)
завершился `success`: JUnit artifact `10811459491`, ZIP SHA256
`8531d38f0dd7d09cdcb902a9462c738c3c279cccf475f775b3d482f3a96e1bcc`
сверен с digest GitHub, 2331 тест, 0 failures/errors/skipped. Редкий timeout
одного теста на более раннем commit остаётся открытым в
[issue #25](https://github.com/DmitrL-dev/1cai-public/issues/25); последующие
зелёные прогоны не доказывают отсутствия этой нестабильности.

Типовые `.cf/.cfe`, расширения, формы/СКД, живая рабочая ИБ, внешний
конкурентный writer, публичный HTTPS/DNS и служба Windows остаются вне
принятого охвата. Production deployment требует отдельной приёмки и разрешения
владельца. Байтная воспроизводимость ZIP между Windows-машинами также не
заявляется: совпали 39/41 внутренних файлов, включая wheel/sdist/scanner, а
два provenance-файла различались.

## Предыдущий выпуск 23 сентября 2026 — core dev10 и Companion 0.1.10

Предыдущая пара раннего доступа: [core `0.1.0.dev10`](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev10)
и [Companion `0.1.10`](https://github.com/DmitrL-dev/1cai-public/releases/tag/companion-v0.1.10).
[Манифест core](../../releases/core/0.1.0.dev10/manifest.json) привязывает
ZIP с SHA256 `11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`
к исходному коммиту `ef0501b` и успешным [push](https://github.com/DmitrL-dev/1cai-public/actions/runs/35827291776)
и [PR](https://github.com/DmitrL-dev/1cai-public/actions/runs/35827295021)
прогонам Product CI. В обоих JUnit — 2327 Python-тестов без ошибок и пропусков;
Node и Go, воспроизводимая сборка, офлайн-установка, snapshot comparison и
observer прошли. Независимая проверка ZIP на фиксированном томе сверила 40
файлов и открыла 32 MCP-инструмента. Wheel из ZIP установлен отдельно и прошёл
пять локальных TLS-тестов. VSIX размером 208263 байта совпал с зафиксированным
SHA256 `b136bc63c63130d61709724f7e52904eb549120016372caee7df330f93193f25`.

Dev10 добавляет ASGI-границу `POST /notifications` к durable digest-приёмнику.
Локальная отправка через TLS проверена с Uvicorn `0.52.4` и
`httptools==0.8.0`; другой HTTP-парсер требует собственной wire-проверки.
Публичный адрес, DNS, сертификаты, секреты, Windows-служба, восстановимое
событие и бизнес-обработка ровно один раз не приняты. Выпуск не разрешает
production deployment и не квалифицирует типовые конфигурации или живую ИБ.

После публикации установленный core dev10 из принятого ZIP также прошёл
[нативную проверку BSL apply/Undo](PROPOSAL-LIVE-APPLY.md#installed-dev10-follow-up-on-native-1c)
на новой собственной файловой базе 1С 8.3.27.2342. Применённый модуль вернул
43, после Undo и повторной загрузки — 42; 11 шагов завершились без ошибки,
исходный inventory и UUID сохранились. [Машинная квитанция](evidence/proposal-live-native-dev10-20260923.json)
связывает артефакт релиза, установленную версию, платформу и результаты. Это
дополнительная проверка после выпуска; опубликованные ZIP и манифест не менялись.
Один синтетический модуль не квалифицирует типовые конфигурации или живую ИБ.

Установленный Core dev10 после выпуска прошёл ещё одну сквозную проверку:
[свежий EDT/MCP preview → live Designer XML writer → 1С/YAxUnit → CAS undo](EDT-LIVE-NATIVE-DEV10.md).
EDT 2026.1.3 действительно создал новый preview в собственном тестовом
профиле; пять native шагов завершились с кодом 0, пять положительных
бизнес-фаз прошли, а чужой UUID вызвал ожидаемый failure. Полный inventory
пяти файлов после Undo совпал с исходным. Подробные границы и
[машинная квитанция](evidence/edt-live-native-dev10-20260924.json) доступны
отдельно; опубликованный ZIP и манифест не менялись.

Опубликованный Companion 0.1.10 также прошёл отдельный
[сценарий редактор → установленный core dev10 → 1С/YAxUnit](EDITOR-TESTS.md):
редактор выбрал сохранённую ревизию 1 при актуальной ревизии 2, baseline дал
один ожидаемый failure, candidate — один passed в отдельных файловых базах.
Новый процесс редактора после отключения профиля прочитал тот же результат без
повторного запуска. [Ограниченная квитанция](evidence/tests-editor-dev10-20260923.json)
связывает публичный VSIX, установленный wheel, платформу, профиль, отчёты и
тестовый harness. Это локальное синтетическое доказательство; runtime редактора
не полностью закреплён, а live apply и типовые конфигурации не проверены.

## Предыдущий выпуск 23 сентября 2026 — core dev9 и Companion 0.1.9

Предыдущая пара раннего доступа: core `0.1.0.dev9` и Companion `0.1.9`.
[Манифест core](../../releases/core/0.1.0.dev9/manifest.json) привязывает
архив, wheel и sdist к точному коммиту `d0a86f6e` и успешному
[Product CI](https://github.com/DmitrL-dev/1cai-public/actions/runs/35812232162).
Два запуска CI для этого коммита завершились успешно; push-отчёт содержит
2298 Python-тестов без ошибок и пропусков, Node и Go проверки прошли.
Скачанный ZIP отдельно подтвердил SHA256, инвентарь и офлайн-работу
установленных CLI/MCP на фиксированном локальном томе; доступно 32 инструмента.

Dev9 включает ограниченные live writers для одного Designer XML
`rename_catalog_attribute` и одного существующего BSL-файла. Их журнал,
Undo и Recover проверяют привязку операции, исходный inventory и sealed
backup; прерванные временные квитанции согласуются после проверки. Для
атомарной замены исходное дерево и state-root должны быть на одном томе.
Companion 0.1.9 добавляет профиль dev9; новая
[крупная схема](../assets/how-rentgen-works.svg) объясняет путь от выгрузки до
решения о правке. Это не полная продуктовая приёмка и не production deployment.

После публикации dev9 установленный core из принятого офлайн-ZIP прошёл
[связанную нативную проверку прямого BSL writer](PROPOSAL-LIVE-APPLY.md#installed-dev9-and-native-1c-check)
на новой собственной файловой базе 1С 8.3.27.2342. Применённый исходник дал
результат приложения 43, после Undo и повторной загрузки — 42; обе проверки
конфигурации и UUID прошли, полный исходный inventory восстановлен. Точная
[машинная квитанция](evidence/proposal-live-native-dev9-20260923.json) связывает
артефакт релиза, установленную версию, платформу и 11 нативных шагов. Это
один синтетический модуль; матрица типовых конфигураций и живая ИБ не приняты.

## Контракт core dev10 — локальный HTTPS-приём уведомлений

В опубликованном core dev10 `NotificationReceiverASGI` предоставляет точный маршрут
`POST /notifications` поверх существующего SQLite-приёмника. До записи
проверяются переданные ASGI заголовки, `Content-Length`, лимит и завершение тела,
HTTPS-схема и успешный lifespan startup. Проверенный host закрепляет
Uvicorn/httptools и отклоняет неоднозначные заголовки ещё при HTTP-разборе;
`h11` для этого контракта не принят. Локальный TLS тест отправляет
уведомление действующим `WebhookAdapter`, проверяет сертификат, отказ обычного
HTTP и повтор после открытия базы заново. Принятие 204 означает сохранённую
квитанцию с хэшем, а не обработанное бизнес-событие. Публичный адрес,
сертификаты, секреты и Windows-служба требуют отдельной приёмки. Dev10 имеет
собственный CI, проверенный офлайн-комплект и отдельный GitHub Release;
предыдущий dev9 не содержит ASGI-границу.

## Дополнение к кандидату 15 сентября 2026 — receiver core

В текущем development-кандидате появился bounded receiver-side контракт для
Git watcher outbox. `NotificationReceiver` проверяет bearer-токен, строгий
idempotency key, JSON/UTF-8 и лимит тела, а затем сохраняет только canonical
payload digest в schema-versioned SQLite. Повтор того же ключа с тем же envelope
даёт `duplicate`/204, повтор с другим envelope — `conflict`/409; параллельные
повторы сериализуются транзакцией. Проверяются определения таблиц/индекса,
все receipts и отсутствие неожиданных triggers/views; unsafe paths/sidecars,
исчерпанный лимит и недоступное состояние блокируют запрос. Локальный injected
outbox round trip подтверждает повтор после потерянного ответа и открытия
receiver заново. Сохраняется digest receipt; обработка бизнес-события в той же
транзакции и восстановимое тело события отсутствуют. Core не открывает
сокет и не регистрирует Windows-службу: live HTTPS endpoint, TLS/DNS policy,
secret provisioning и SCM deployment ещё требуют host-specific приёмки.

## Дополнение к кандидату 15 сентября 2026

В текущем кандидате появился отдельный bounded live writer для одного
поддержанного сценария `rename_catalog_attribute` в одном базовом
`designer_xml` слое. Он принимает только уже прошедший read-only preflight,
сохраняет sealed intent/result journal вне исходника, сериализует операции OS
lock, проверяет CAS по байтам, публикует изменения атомарно и поддерживает
явные `undo`/`recover` к исходному состоянию. CLI и MCP вызывают один и тот же
контракт; неизвестные пути, независимая или неподтверждённая нормализация,
расширения, формы/СКД и типовые
конфигурации остаются fail-closed. Это первая принятая файловая live-граница,
но не native writer для EDT/Конфигуратора или базы 1С.

Для текущей development-ветки schema 3 добавляет bounded
автономную подготовку snapshot доверенным локальным scanner перед Git-аудитом:
права и ancestry проверяются до capture, подготовленный Git observation
перепроверяется перед анализом, unchanged-события не заполняют outbox, а
matching owner receipt переиспользуется после рестарта. Повреждённый durable
commit отклоняется до capture; schema 1/2 и прежние scheduler defaults сохранены.
Проверены race, отзыв прав, restart, recovery, scheduler stop и forwarding
политики уведомлений. Это по-прежнему bounded/read-only режим: live SCM,
запись в рабочую конфигурацию 1С и exactly-once доставка не приняты.

Для принятого commit `4cb07f29111c75e883ec17682b1395dfa9f9a84e`
(tree `01c6b0888e6de7a423144cef918d4f0c5f002fff`) локальный
`python -m pytest -q` завершился: **2203 passed, 3 skipped** за 1552,29 с.
Три Windows symlink-теста ожидаемо пропущены из-за WinError 1314.
На момент этой сверки Product CI для этого SHA ещё выполнялся:
[push](https://github.com/DmitrL-dev/1cai-public/actions/runs/34947939321) и
[PR](https://github.com/DmitrL-dev/1cai-public/actions/runs/34947943381).
Эти результаты относятся только к указанному commit и не подтверждают
CI последующих изменений или production-готовность.
Рыночная карта проверена 15 сентября по первичным источникам и обновлена в
[COMPETITOR-MATRIX.md](COMPETITOR-MATRIX.md); open/self-hosted/headless и
model-agnostic по отдельности не считаются уникальным преимуществом.

В текущем блоке `edt-inventory` получил профиль `edt_identity_v2` для реальной
формы EDT `MetaDataObject/*.xml`: UUID и имена корневых объектов и прямых
`ChildObjects` проверяются в namespaced XML, а отдельные формы/команды получают
владельца только из уже проверенного родительского descriptor-файла. Legacy
`.mdo` продолжает обслуживаться профилем v1; смешение форматов, неизвестные
UUID-контейнеры и отсутствующий владелец отклоняются. Это read-only evidence;
bounded live writer покрывает только отдельный `designer_xml` сценарий выше и
не означает полную поддержку форм/СКД.

## Дополнение к кандидату 14 сентября 2026

Для кандидата `1a1015b12b7d2271a56ec821c1037dd56a128064` собрано 1936 тестов;
полный локальный прогон дал 1933 успешных теста и 3 ожидаемых пропуска на Windows
без права создавать симлинки. Эти числа привязаны к указанному SHA и не
подменяют проверку последующих изменений. Product CI запускается для
каждого SHA в [публичном workflow](https://github.com/DmitrL-dev/1cai-public/actions/workflows/core-ci.yml).
Три Windows symlink-теста могут
пропускаться из-за отсутствия privilege. Кандидат включает bounded foreground
service-host, explicit SCM installer planning и явную freshness-policy для
runtime-метрик поверх публичного owner-report CLI с проверкой опубликованного snapshot и выделенным
`<state-root>\owner-reports`, immutable receipts и bounded summary для списка.
Read-only EDT inventory теперь связывает проверенные UUID, прямых XML-владельцев
и декларацию слоя с `SourceRef`. Эти partial evidence доступны через
[`edt-inventory`](EDT-INVENTORY-IDENTITY.md#local-cli): явный опубликованный
snapshot, только `project:read`, ограниченные входы и JSON до 8 MiB, без записи
или native-вызовов. Three-way plan дополнительно показывает
атомарные UUID-bound области BSL, форм и СКД с явными
`supported`/`conflict`/`unsupported` причинами, а для доказанно раздельных
изменений прямых Designer `Properties` — bounded in-memory candidate с
сохранением XML-фрагментов. Для выбранных EDT Catalog `.mdo` добавлено
read-only child-owner evidence: UUID реквизита, непосредственный owner, XML
location и детерминированные structural hashes; смена владельца или типа
отклоняется до классификации. Эти возможности собраны в wheel и
sdist и не меняют live source или базу 1С. Owner report теперь можно собрать
из durable observer findings командой `owner-report-build`, без ручного JSON;
оба runtime loader-а читают
retained-файл по исходному no-follow локатору без предварительного
`Path.resolve()`. Runtime register export adapter проверяет context,
rows↔metrics и canonical source digest; SARIF adapter
импортирует только attested bounded subset внешнего отчёта.

Отдельно на собственной синтетической EDT-фикстуре проверен нативный
`ibcmd`-цикл `infobase create → config import → config export` с сохранением
UUID справочника, реквизита и формы; [сводка и границы](EDT-COMMAND-BOUNDARY.md).
Это evidence для конкретной среды и fixture, а не продуктовый исполнитель.

В этом срезе добавлены schema 2/3 composition root для bounded Git → BSL →
findings/outbox → owner-report аудита и frozen retained-register producer для
одного offline runtime export. Schema 3 также подготавливает принадлежащий
snapshot локальным scanner перед аудитом. Оба режима по умолчанию fail-closed и
не включают live 1С, сеть или произвольный процесс.

Native EDT adapter теперь принят для повторения выбранного preview и apply/undo
в новой принадлежащей файловой копии: admission выполняется до его журналов,
readback связывает native preview и workspace receipt, а после undo проверяется
исходный inventory. Это не запись в рабочую конфигурацию и не live apply.

Отдельно [проверен консольный запуск Source Observer установленного Core dev10](SERVICE-CONSOLE-NATIVE-DEV10.md):
новый собственный проект и BSL-модуль дали один snapshot и durable report;
перезапуск не создал дублей, чужой project ID был отвергнут, а lease и источник
сохранились. [Квитанция](evidence/service-console-native-dev10-20260924.json)
связывает результат с точным ZIP/wheel/scanner релиза. Это проверка отдельного
процесса в console mode, без установки службы в SCM.

В этом срезе three-way materializer принимает только доказанно раздельные
прямые BSL `Properties`: результат ограничен исходными XML-фрагментами и
bounded digest, а формы, СКД, расширения и неизвестные области остаются
блокирующими. Workspace receipts получили привязку к root/marker, строгую
проверку соседних и подменённых журналов, явную legacy-политику и Windows
admission mutex с одинаковой identity для обычного и `\\?\\` пути. CLI может
показать bounded список объединённых BSL-областей без выдачи их payload.

Приёмка остаётся частичной: продуктовая запись в рабочую
конфигурацию, типовые `.cf/.cfe`, полноценная семантика расширений, BSL/форм/СКД
round-trip, live SCM daemon/deployment, внешняя доставка уведомлений и Spectorn
adapter ещё не подтверждены. Native ServiceMain/SCM boundary теперь есть как
mocked adapter proof, но это не live service acceptance. До таких evidence
нельзя объявлять dev9 production-ready.

Для dev9 выполнен [эксперимент редактирования метаданных
через EDT](EDT-METADATA-EXPERIMENT.md): реквизит и поле формы, каскадное
переименование, проверка экспорта платформой и восстановление тестового проекта.
Отдельно [проверена сохранность трёх записей](METADATA-MIGRATION.md) при импорте,
переименовании и возврате схемы на собственной фикстуре 1С/YAxUnit.
Продуктовый preview уже связывается с бизнес-доказательством; [журнал подготовки
apply](METADATA-APPLY.md) проверяет точный preview, head, права и живые байты.
[Workspace writer](METADATA-WORKSPACE.md) применяет candidate и выполняет undo
с проверкой inventory только в отдельно принадлежащей копии. Перед undo проверяется
полный backup; он сохраняется при отмене и её явном восстановлении к original.
Отдельный OS lock сериализует apply/undo/recovery вызовы самого workspace API.
Внешняя конкурентная запись между проверкой и заменой файлов пока не защищена;
новый writer защищает только явно поддержанный `designer_xml` source tree и не
меняет native EDT/Конфигуратор или базу 1С.
Выпуски dev8/0.1.8 этой возможностью не дополняются задним числом.

В core `0.1.0.dev8` доступны сравнение снимков и
[observer выгрузки](OBSERVER.md). Проверены отдельные процессы установленного
wheel с реальным scanner: блокировка конкурирующего worker, освобождение после
завершения процесса, сохранённые отчёты и отсутствие повторного захвата
неизменных источников. Восстановление после публикации и отзыв прав покрыты
регрессионными тестами. Это часть O1, без диагностики качества и бизнес-метрик.
Историческая пара раннего доступа: core dev8 и companion 0.1.8.
[Манифест](../../releases/core/0.1.0.dev8/manifest.json) фиксирует коммит сборки
и хэши; [проверка выпуска](evidence/release-dev8.json) — доставку и установку.
Сборка офлайн-комплекта теперь доступна в публичном репозитории: две сборки
wheel/sdist/scanner совпали побайтно, комплект с 30 wheels зависимостей прошёл
установку без индекса пакетов и сценарий CLI/MCP в новом окружении.
[Инструкция](CORE-OFFLINE-KIT.md) и [хэши проверки](evidence/core-kit-dev8-windows-py311.json)
относятся к конкретному commit; это не проверка на чистой машине и не полный выпуск.
Для dev8 собран companion 0.1.5 разработки с проверкой сохранённой версии
черновика установленной 1С и чтением результата по UUID. Проверены настоящий
клиент 8.3.27.2342 и открытие отчётов в новом процессе VSCodium;
[границы проверки](EDITOR-PLATFORM-CHECK.md) сохраняются.
Companion 0.1.7 разработки добавляет BSL-проверку сохранённой версии и чтение
отчёта после перезапуска. Реальный редактор подтвердил замечание в старой версии
и чистую диагностику исправленной версии; [условия и границы](EDITOR-BSL-CHECK.md).
YAxUnit 25.12 подтвердил fail/pass одного синтетического теста на новой базе
8.3.27.2342. Клиент 1С возвращает 0 даже при провале теста, поэтому проверяется
точный JUnit и отдельный exitCode. [Профиль и ограничения](YAXUNIT-PLATFORM-PROFILE.md):
В dev8 подтверждены [регистрация профиля и запуск предложения через установленный CLI](TEST-PROFILES.md): две отдельные базы, fail/pass, восстановление результата и запрет нового запуска отключённого профиля. В [companion 0.1.8](EDITOR-TESTS.md) реальный редактор проверил историческую версию при наличии более новой и восстановил отчёт после отключения профиля без нового запуска. Приёмка на типовых конфигурациях пока не выполнена.

Нативные проверки используют [владение деревом процессов, общий слот проекта и контроль диска](NATIVE-RESOURCES.md). На установленной 1С подтверждены отказ конкурентному запуску и очистка служебных журналов ibcmd: вместо 1,12 ГБ осталось около 44 МБ. Для retained-run добавлены явные admin-only CLI/API архивирование и audit с сохранением баз и отчётов; архив освобождает только логический слот, физический reclaim и изоляция BSL от ОС остаются открытыми задачами.

| Компонент | Подтверждено | Ограничение |
| --- | --- | --- |
| Core 0.1.0.dev10 | Всё принятое в dev9; ASGI-приём `POST /notifications`, durable digest-квитанция, локальная TLS-проверка установленного wheel, отдельная нативная проверка BSL apply/Undo и [console mode Source Observer](SERVICE-CONSOLE-NATIVE-DEV10.md) после выпуска | Требует отдельно настроенного Uvicorn/httptools host; публичный HTTPS/DNS/SCM deployment, типовые конфигурации и живая ИБ не приняты |
| Companion 0.1.10 | Побайтно воспроизводимый VSIX, профиль для dev10, сохранение ранее поддержанных сценариев редактора; отдельный нативный editor-to-platform прогон опубликованного VSIX с установленным core dev10 и восстановлением отчёта | Требует нового доверенного профиля; проверен один синтетический модуль, runtime редактора не полностью закреплён, типовые конфигурации и live apply не приняты |
| Core 0.1.0.dev9 | Отдельная установка, снимки, исходники, граф, права, черновики, MCP, BSL; ограниченные live writers и нативная проверка BSL apply/undo на собственном синтетическом проекте | Windows x64 / Python 3.11; типовые конфигурации и живая ИБ не приняты |
| Companion 0.1.9 | Сборка VSIX с фиксированным SHA256, просмотр и сравнение, локальная правка, чтение квитанций | Требует доверенного отдельного профиля |
| Локальная модель | Один искусственный сценарий Qwen3.5:9b с независимой проверкой BSL | Не доказывает качество на произвольных задачах |
| Ежедневная разработка dev8 | AI-правка, ручное исправление новой ревизией, конфликт версий, нативная проверка и восстановление проверены в редакторе | [AI-ошибка сохраняется](DAILY-DEVELOPMENT-ACCEPTANCE.md); [исправление человеком проверено](MANUAL-DRAFT-EDIT.md). Синтетический YAxUnit принят отдельно; бизнес-покрытие и применение не приняты |
| Реальная платформа 1С | 8.3.27.2342: нативный общий модуль, проверка ошибочного BSL, исполнение 42 → отказ/42 → исправление/43, сохранение UUID; отдельная запись/чтение/переименование/удаление данных в синтетическом каталоге ([evidence](NATIVE-BUSINESS-ROUNDTRIP-20260913.md)) | Собственные синтетические сценарии; [полная приёмка не завершена](PLATFORM-ACCEPTANCE.md) |
| Прямое изменение метаданных | EDT preview Article → SKU, два diff, проверка UUID/формы, сохранность трёх записей при миграции/возврате; owned `ibcmd` create/import/export round-trip с structural evidence; preflight и workspace writer с проверкой inventory, backup, re-read, undo conflict, привязанными receipts, legacy policy и явным recovery; native business roundtrip и product apply/undo receipt подтверждены для отдельной принадлежащей копии; bounded live Designer XML apply/undo на зарегистрированном дереве прошёл [сквозную проверку установленного dev10 и 1С/YAxUnit](METADATA-LIVE-NATIVE-DEV10.md) на синтетическом owned source; direct BSL proposal writer добавлен для одного существующего файла с journal/CAS/recovery и тестами | Обновление живой ИБ через EDT/1С, внешний concurrent CAS, произвольные `.cf/.cfe`, расширения, формы/СКД и матрица типовых конфигураций не приняты |
| Обновления конфигураций | Path-bytes и UUID-aware Designer XML three-way plan с bounded хэшами, явными конфликтами и evidence по прямым свойствам (`same_change`/`disjoint_changes`/`overlap_conflict`); для квалифицированного `disjoint_changes` прямых `Properties` доступен in-memory candidate с сохранением namespace/QName и digest; для BSL есть bounded composite merge с owner/path binding; для выбранных EDT Catalog `.mdo` есть read-only child-owner evidence и fail-closed transfer/type checks, а EDT identity plan сравнивает partial UUID/owner/layer evidence | Расширения, полный BSL/формы/СКД round-trip, полноценная схема Designer, типовые конфигурации, тестовая база, backup/rollback, native validity и запись three-way candidate не приняты |
| Проверка предложения платформой | В dev8: установленный CLI проверил корректное/ошибочное BSL-предложение на сохранённой конфигурации; в исходной ветке после dev8 compile/YAxUnit API используют bounded native admission/retention ([границы](NATIVE-RESOURCES.md)) | Один Designer XML слой; компиляция без бизнес-тестов и применения |
| Observer | Опрос выгрузки, journal/recovery и durable findings; [установленный Core dev10 выполнил console mode](SERVICE-CONSOLE-NATIVE-DEV10.md) в отдельном процессе с первым report, повторным запуском и bounded отказом; schema 2/3 composition root связывает GitWatcherScheduler, read-only BSL Git adapter, owner-report store и atomic local outbox с bounded cooperative stop; schema 3 добавляет trusted snapshot capture, ancestry/race/revocation gates и receipt reuse; per-commit snapshot binding, bounded Git/snapshot source evidence, read-only BSL-LS adapter, bounded SARIF subset, native ServiceMain/SCM boundary proof, явный SCM installer plan и receiver-side SQLite idempotency/conflict contract | Нет live SCM deployment/daemon acceptance, public HTTPS/DNS host acceptance (local TLS receiver dev10 checked separately), полного Git tree/temporal evidence, producer-specific Sonar/Vanessa/YAxUnit execution и общей приёмки O1 |
| Бизнес-отчёты | Bounded owner-report schema с quality/runtime provenance, durable immutable receipts и fail-closed incomplete/not_available статусами; quality не публикуется без явной binding; `owner-report-build` собирает отчёт из durable observer findings; runtime loader проверяет период и freshness; onec-register-export-v1 adapter и frozen retained-register producer связывают rows↔metrics, canonical source digest, период и expected metric set | Live 1С producer, независимая методика O2 и commit↔snapshot/runtime evidence не приняты; числовые бизнес-метрики не объявляются достоверными только по offline fixture |
| Spectorn в адаптере | Не подключён | Защита трафика этого сценария не подтверждена |

Первоначально в публичное дерево перенесён source distribution core dev7;
перечень исходных файлов и хэшей — `releases/public-source-import.json`.
Локальные пути, ключи и журналы проектов не являются частью поставки.
Тесты адаптированы для запуска из самостоятельного публичного checkout.

Приёмка расширения и её границы описаны в [EDITOR-REPAIR-ACCEPTANCE.md](EDITOR-REPAIR-ACCEPTANCE.md).
Указанные там локальные отчёты — свидетельства разработки, а не включённые
в репозиторий пользовательские данные. Автоматические проверки публичного дерева
доступны в GitHub Actions; выпуск компонента проходит отдельную проверку хэша.

## EDT identity plan — 15 сентября 2026

Для трёх сохранённых inventory добавлен [EDT identity three-way plan](EDT-IDENTITY-THREE-WAY.md)
и read-only CLI `edt-inventory-plan`: проверенные bindings UUID/owner/layer,
явные конфликты и unsupported-причины, ограничение JSON 8 MiB. Это сравнение
предоставленного partial evidence без материализации или native validation.

## Native apply/undo и бизнес-данные — 15 сентября 2026

В этот же день повторно подтверждена установленная платформа: native
Designer XML/BSL сценарий и YAxUnit 25.12 fail/pass завершились на новых
файловых базах; хэши и коды шагов сохранены в
[native evidence](evidence/native-platform-8.3.27.2342-20260915.json) и
[YAxUnit evidence](evidence/yaxunit-25.12-platform-20260915.json). Это усиливает
матрицу версии 8.3.27.2342, но не расширяет её до типовых конфигураций, форм,
поставщика или rollback.

Связанный запуск `metadata_native_apply` и 1С/YAxUnit теперь сохранён в
[METADATA-NATIVE-BUSINESS.md](METADATA-NATIVE-BUSINESS.md) и его
[машинной квитанции](evidence/metadata-native-apply-business-20260915.json).
Apply выполнен в новой принадлежащей рабочей копии, после чего CAS undo и
recovery вернули исходный inventory; рабочее дерево не изменялось. На тех же
байтах 1С 8.3.27.2342/YAxUnit 25.12 подтвердили три записи и положительные
переходы схемы, а намеренно изменённый UUID дал ожидаемую ошибку данных.

Это закрывает только доказательство owned-copy apply/undo и привязку receipt к
бизнес-проверке. Отдельно bounded live Designer XML apply/undo проверен на
зарегистрированном дереве принадлежащего профиля; обновление живой ИБ,
произвольные `.cf/.cfe`,
расширения, формы/СКД и полная матрица типовых конфигураций остаются отдельными
блокирующими направлениями.

## Прямая запись Designer XML установленным dev10 — 23 сентября 2026

На фиксированном локальном томе проверена цепочка retained preview → live
writer → загрузка изменённого источника в новую файловую базу 1С → native
check/round-trip → CAS undo. Пять native шагов завершились с кодом 0;
бизнес-фазы на идентичных original/candidate inventory прошли, кроме
ожидаемого отказа при чужом UUID. Подробности и границы опыта — в
[отчёте](METADATA-LIVE-NATIVE-DEV10.md) и
[машинной квитанции](evidence/metadata-live-native-dev10-20260923.json).
