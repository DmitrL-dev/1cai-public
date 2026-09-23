# Состояние публичной поставки — 23 сентября 2026

Актуальная [карта рынка и выбранное направление](COMPETITOR-MATRIX.md)
поясняют, какие соседние инструменты мы интегрируем и какие незакрытые
сценарии остаются нашим преимуществом.

[Матрица совместимости и evidence](CONFIGURATION-COMPATIBILITY.md) отделяет
синтетический EDT read-only contract от исторических native экспериментов;
добавление corpus не квалифицирует типовые `.cf/.cfe` и live apply.

## Выпуск 23 сентября 2026 — core dev9 и Companion 0.1.9

Текущая пара раннего доступа: core `0.1.0.dev9` и Companion `0.1.9`.
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

## Кандидат core dev10 / Companion 0.1.10 — локальный HTTPS-приём уведомлений

В development-ветке `NotificationReceiverASGI` предоставляет точный маршрут
`POST /notifications` поверх существующего SQLite-приёмника. До записи
проверяются переданные ASGI заголовки, `Content-Length`, лимит и завершение тела,
HTTPS-схема и успешный lifespan startup. Проверенный host закрепляет
Uvicorn/httptools и отклоняет неоднозначные заголовки ещё при HTTP-разборе;
`h11` для этого контракта не принят. Локальный TLS тест отправляет
уведомление действующим `WebhookAdapter`, проверяет сертификат, отказ обычного
HTTP и повтор после открытия базы заново. Принятие 204 означает сохранённую
квитанцию с хэшем, а не обработанное бизнес-событие. Публичный адрес,
сертификаты, секреты и Windows-служба требуют отдельной приёмки. Этот код пока
не входит в опубликованный dev9; публикация dev10 требует собственного CI,
проверенного офлайн-комплекта и отдельного GitHub Release.

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
| Core 0.1.0.dev9 | Отдельная установка, снимки, исходники, граф, права, черновики, MCP, BSL; ограниченные live writers и нативная проверка BSL apply/undo на собственном синтетическом проекте | Windows x64 / Python 3.11; типовые конфигурации и живая ИБ не приняты |
| Companion 0.1.9 | Сборка VSIX с фиксированным SHA256, просмотр и сравнение, локальная правка, чтение квитанций | Требует доверенного отдельного профиля |
| Локальная модель | Один искусственный сценарий Qwen3.5:9b с независимой проверкой BSL | Не доказывает качество на произвольных задачах |
| Ежедневная разработка dev8 | AI-правка, ручное исправление новой ревизией, конфликт версий, нативная проверка и восстановление проверены в редакторе | [AI-ошибка сохраняется](DAILY-DEVELOPMENT-ACCEPTANCE.md); [исправление человеком проверено](MANUAL-DRAFT-EDIT.md). Синтетический YAxUnit принят отдельно; бизнес-покрытие и применение не приняты |
| Реальная платформа 1С | 8.3.27.2342: нативный общий модуль, проверка ошибочного BSL, исполнение 42 → отказ/42 → исправление/43, сохранение UUID; отдельная запись/чтение/переименование/удаление данных в синтетическом каталоге ([evidence](NATIVE-BUSINESS-ROUNDTRIP-20260913.md)) | Собственные синтетические сценарии; [полная приёмка не завершена](PLATFORM-ACCEPTANCE.md) |
| Прямое изменение метаданных | EDT preview Article → SKU, два diff, проверка UUID/формы, сохранность трёх записей при миграции/возврате; owned `ibcmd` create/import/export round-trip с structural evidence; preflight и workspace writer с проверкой inventory, backup, re-read, undo conflict, привязанными receipts, legacy policy и явным recovery; native business roundtrip и product apply/undo receipt подтверждены для отдельной принадлежащей копии; bounded live Designer XML apply/undo на зарегистрированном дереве подтверждён отдельным smoke; direct BSL proposal writer добавлен для одного существующего файла с journal/CAS/recovery и тестами | Обновление живой ИБ через EDT/1С, внешний concurrent CAS, произвольные `.cf/.cfe`, расширения, формы/СКД и матрица типовых конфигураций не приняты |
| Обновления конфигураций | Path-bytes и UUID-aware Designer XML three-way plan с bounded хэшами, явными конфликтами и evidence по прямым свойствам (`same_change`/`disjoint_changes`/`overlap_conflict`); для квалифицированного `disjoint_changes` прямых `Properties` доступен in-memory candidate с сохранением namespace/QName и digest; для BSL есть bounded composite merge с owner/path binding; для выбранных EDT Catalog `.mdo` есть read-only child-owner evidence и fail-closed transfer/type checks, а EDT identity plan сравнивает partial UUID/owner/layer evidence | Расширения, полный BSL/формы/СКД round-trip, полноценная схема Designer, типовые конфигурации, тестовая база, backup/rollback, native validity и запись three-way candidate не приняты |
| Проверка предложения платформой | В dev8: установленный CLI проверил корректное/ошибочное BSL-предложение на сохранённой конфигурации; в исходной ветке после dev8 compile/YAxUnit API используют bounded native admission/retention ([границы](NATIVE-RESOURCES.md)) | Один Designer XML слой; компиляция без бизнес-тестов и применения |
| Observer | Опрос выгрузки, journal/recovery и durable findings; schema 2/3 composition root связывает GitWatcherScheduler, read-only BSL Git adapter, owner-report store и atomic local outbox с bounded cooperative stop; schema 3 добавляет trusted snapshot capture, ancestry/race/revocation gates и receipt reuse; per-commit snapshot binding, bounded Git/snapshot source evidence, read-only BSL-LS adapter, bounded SARIF subset, native ServiceMain/SCM boundary proof, явный SCM installer plan и receiver-side SQLite idempotency/conflict contract | Нет live SCM deployment/daemon acceptance, live HTTPS receiver/TLS/DNS acceptance, полного Git tree/temporal evidence, producer-specific Sonar/Vanessa/YAxUnit execution и общей приёмки O1 |
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
