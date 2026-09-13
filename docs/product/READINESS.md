# Состояние публичной поставки — 14 сентября 2026

Актуальная [карта рынка и выбранное направление](COMPETITOR-MATRIX.md)
поясняют, какие соседние инструменты мы интегрируем и какие незакрытые
сценарии остаются нашим преимуществом.

## Дополнение к кандидату 14 сентября 2026

В текущем исходном кандидате собрано 1190 тестов; Product CI запускается для
каждого SHA в [публичном workflow](https://github.com/DmitrL-dev/1cai-public/actions/workflows/core-ci.yml).
Три Windows symlink-теста могут
пропускаться из-за отсутствия privilege. Кандидат включает bounded foreground
service-host, explicit SCM installer planning и явную freshness-policy для
runtime-метрик поверх публичного owner-report CLI с проверкой опубликованного snapshot и выделенным
`<state-root>\owner-reports`, immutable receipts и bounded summary для списка.
Read-only EDT inventory теперь связывает проверенные UUID, прямых XML-владельцев
и декларацию слоя с `SourceRef`; three-way plan дополнительно показывает
атомарные UUID-bound области BSL, форм и СКД с явными
`supported`/`conflict`/`unsupported` причинами. Эти возможности собраны в wheel и
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

В этом срезе добавлены schema 2 composition root для bounded Git → BSL →
findings/outbox → owner-report аудита и frozen retained-register producer для
одного offline runtime export. Оба режима по умолчанию fail-closed и не
включают live 1С, сеть или произвольный процесс.

Приёмка остаётся частичной: продуктовая запись в рабочую
конфигурацию, типовые `.cf/.cfe`, полноценная семантика расширений, BSL/форм/СКД
round-trip, live SCM daemon/deployment, внешняя доставка уведомлений и Spectorn
adapter ещё не подтверждены. Native ServiceMain/SCM boundary теперь есть как
mocked adapter proof, но это не live service acceptance. До таких evidence нельзя повышать dev8 prerelease
или объявлять production-ready.

В ветке `codex/edt-metadata-dev9` выполнен [эксперимент редактирования метаданных
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
live source и база 1С намеренно не меняются.
Выпуски dev8/0.1.8 этой возможностью не дополняются задним числом.

В core `0.1.0.dev8` доступны сравнение снимков и
[observer выгрузки](OBSERVER.md). Проверены отдельные процессы установленного
wheel с реальным scanner: блокировка конкурирующего worker, освобождение после
завершения процесса, сохранённые отчёты и отсутствие повторного захвата
неизменных источников. Восстановление после публикации и отзыв прав покрыты
регрессионными тестами. Это часть O1, без диагностики качества и бизнес-метрик.
Текущая пара раннего доступа: core dev8 и companion 0.1.8.
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

Нативные проверки используют [владение деревом процессов, общий слот проекта и контроль диска](NATIVE-RESOURCES.md). На установленной 1С подтверждены отказ конкурентному запуску и очистка служебных журналов ibcmd: вместо 1,12 ГБ осталось около 44 МБ. Базы и отчёты сохраняются; длительное архивирование и изоляция BSL от ОС остаются открытыми задачами.

| Компонент | Подтверждено | Ограничение |
| --- | --- | --- |
| Core 0.1.0.dev8 | Отдельная установка, снимки, исходники, граф, права, черновики, MCP, BSL | Windows x64 / Python 3.11; применение не принято |
| Companion 0.1.8 | Сборка VSIX с фиксированным SHA256, просмотр и сравнение, локальная правка, чтение квитанций | Требует доверенного отдельного профиля |
| Локальная модель | Один искусственный сценарий Qwen3.5:9b с независимой проверкой BSL | Не доказывает качество на произвольных задачах |
| Ежедневная разработка dev8 | AI-правка, ручное исправление новой ревизией, конфликт версий, нативная проверка и восстановление проверены в редакторе | [AI-ошибка сохраняется](DAILY-DEVELOPMENT-ACCEPTANCE.md); [исправление человеком проверено](MANUAL-DRAFT-EDIT.md). Синтетический YAxUnit принят отдельно; бизнес-покрытие и применение не приняты |
| Реальная платформа 1С | 8.3.27.2342: нативный общий модуль, проверка ошибочного BSL, исполнение 42 → отказ/42 → исправление/43, сохранение UUID; отдельная запись/чтение/переименование/удаление данных в синтетическом каталоге ([evidence](NATIVE-BUSINESS-ROUNDTRIP-20260913.md)) | Собственные синтетические сценарии; [полная приёмка не завершена](PLATFORM-ACCEPTANCE.md) |
| Прямое изменение метаданных | EDT preview Article → SKU, два diff, проверка UUID/формы, сохранность трёх записей при миграции/возврате; owned `ibcmd` create/import/export round-trip с structural evidence; preflight и workspace writer с проверкой inventory, backup, re-read, undo conflict и явным recovery; native business roundtrip подтверждает данные после переименования | Внешний concurrent CAS, живая запись через EDT/1С, product apply/undo и матрица типовых конфигураций не приняты |
| Обновления конфигураций | Path-bytes и UUID-aware Designer XML three-way dry-run с bounded хэшами, явными конфликтами и evidence по прямым свойствам (`same_change`/`disjoint_changes`/`overlap_conflict`) | Property/extension/BSL merge semantics, тестовая база, backup/rollback и запись не приняты |
| Проверка предложения платформой | В dev8: установленный CLI проверил корректное/ошибочное BSL-предложение на сохранённой конфигурации; в исходной ветке после dev8 compile/YAxUnit API используют bounded native admission/retention ([границы](NATIVE-RESOURCES.md)) | Один Designer XML слой; компиляция без бизнес-тестов и применения |
| Observer | Опрос выгрузки, journal/recovery и durable findings; schema 2 composition root связывает GitWatcherScheduler, read-only BSL Git adapter, owner-report store и atomic local outbox с bounded cooperative stop; per-commit snapshot binding, bounded Git/snapshot source evidence, read-only BSL-LS adapter, bounded SARIF subset, native ServiceMain/SCM boundary proof и явный SCM installer plan | Нет live SCM deployment/daemon acceptance, live receiver acceptance и дедупликации, полного Git tree/temporal evidence, producer-specific Sonar/Vanessa/YAxUnit execution и общей приёмки O1 |
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
