# Сверка планов и выпуск dev19 / 0.1.20

Это датированная история **компонентного prerelease**, а не план завершения
всего продукта. Текущая цель, реестр 127 требований, все 24 IDE-сценария
и очередь разработки ведутся в [плане полного финального релиза](FULL-FINAL-PLAN.md).
Исторические результаты ниже сохраняют исходные даты, версии и scope.

Дата аудита: 15 октября 2026. Исходная база — `main`
`998e19a4e4234737f7d987e1f1737ab8270b34e6` после PR #98.
Итог: опубликованы **Core dev19 / Companion 0.1.20**, компонентные prerelease.
Core source — [`5eee97ea050c9f4c06eaceb4d191f16868fb0141`](https://github.com/DmitrL-dev/1cai-public/tree/5eee97ea050c9f4c06eaceb4d191f16868fb0141),
дерево `0e1bcfc82561e01091ad4c2a9274738739a982e8` после обычного merge PR #99.
Фактические CI и installation/interop/browser gates связывает
[qualification](../../releases/core/0.1.0.dev19/qualification.json), публичные bytes —
[квитанция публикации](evidence/release-dev19-publication-20261015.json).
Номера dev18 / 0.1.19 остаются у невыпущенного draft #84.
Сам план не подменяет эти записи; старые версии и evidence сохранены.

## Что сделано и что остаётся

| Направление / план | Что есть | Что ещё не принято |
| --- | --- | --- |
| [ROADMAP §1: первый результат](../../ROADMAP.md) | Windows маршрут «выгрузка → снимок → модули», инструкции и опубликованный комплект dev19; offline installation точных файлов в квалификации | Измерение времени и первый результат нового пользователя остаются отдельной незавершённой приёмкой |
| [IDE, 24 сценария](IDE-DEVELOPMENT-PLAN.md) | Макеты; отдельные GUI-срезы поиска, чтения, сравнения | Все 24 сквозных сценария остаются открытыми; выбор оболочки, storage/search/debug, команды и AI benchmark |
| [Локальная правка](LOCAL-REPAIR-PLAN.md) | Парсер, CLI/MCP, история и UI Companion; ручной черновик и точное редактирование PR #76–#79 | Отрицательная AI-приёмка не стала положительной; реальное качество модели и ежедневная работа требуют новых опытов |
| [Снимки и Observer](SNAPSHOT-OBSERVER-PLAN.md) | Завершённый ограниченный план dev8, чтение/сравнение снимков, installed-smoke в CI | Новые пакеты проходят проверку заново; полная переносимость capture/observer не заявлена |
| [Native-платформа](NATIVE-PLATFORM-PLAN.md) | Исторические опыты на 1С 8.3.27.2342 и собственных фикстурах | Формы, расширенная матрица runtime, произвольные конфигурации, полный rollback и новая native-приёмка |
| [EDT adapter](EDT-ADAPTER-PLAN.md) | Профили, исполнитель, SnapshotRef/materialization, preview и ограниченный native опыт dev13 | Типовые конфигурации, общая матрица объектов и квалификация новой установленной поставки |
| [Узкая диагностика](NARROW-DIAGNOSTICS-PLAN.md) | Синтетический Rust kernel и детерминированные контракты | Независимый benchmark, native probes, пользовательский CLI/MCP-сценарий; синтетика не равна продуктовой диагностике |
| [Portable core](PORTABLE-CORE.md) | Linux local state/history/planners и bounded ZIP CLI выпущены экспериментально | Capture, live apply и native 1С на Linux; полноценная macOS-поддержка |
| [Локальный GUI](LOCAL-GUI.md) | PR #83, #85–#99: импорт, поиск, страницы, реквизиты, вхождения, два/три ZIP, отчёты и line diff; финальный Linux supplement и installed HTTP/Rust/browser квалифицированы по квитанциям dev19 | Windows/macOS GUI, рабочее место полной IDE и сквозные сценарии её плана |
| [Обновления](THREE-WAY-UPDATES.md) и [семантика](METADATA-THREE-WAY-SEMANTICS.md) | Ограниченные BSL/XML writers, byte/JSON planners, read-only three-ZIP inventory | Общий предок, семантическое слияние, безопасная загрузка в любую базу и сценарии IDE 04/05 |
| [Git watcher](GIT-WATCHER.md), source-facts PR #84 | Watcher/SCM/Git contracts в main; отдельный source-facts draft | В #84: конфликт lifecycle, полный176/whole-process gate, source cohort и installed-wheel; draft не включён в кандидат |
| Производительность и интеграции | Bounded Rust import и ограниченные замеры; прямой Ollama adapter | Репрезентативные cold/warm benchmark, универсальное ускорение, защищённый маршрут Spectorn |

Наличие кода, старого native-отчёта или одного зелёного теста не закрывает
весь ряд таблицы. Исторические evidence сохраняют свои версии и даты.

## Состав опубликованной пары

- Windows x64 / CPython 3.11: локальное ядро, Go scanner и offline kit;
  исправления после dev17, ручное создание/редактирование черновиков,
  совместимость Companion 0.1.20 в проверенном service/installed CLI сценарии.
- GNU/Linux x86_64 / CPython 3.11 и 3.12: экспериментальное дополнение
  с тем же pure-Python wheel и принятым Rust input core. Новый GUI читает
  ограниченные Designer XML ZIP, показывает поиск/сравнение без записи.
- Новая полная IDE, source-facts PR #84, native 1С бизнес-приёмка, качество AI,
  cold OwnerIPC и полный Linux/macOS продукт не заявляются.

## Gates и фактические записи выпуска

- [x] Сверить remote main, открытые PR/issues и планы. Открытых issues нет;
  #84 остаётся draft с конфликтом и отдельной квалификацией.
- [x] Разделить кандидат и опубликованные пакеты в README и документации.
- [x] Проверить изменения новой версии и release tooling узкими тестами:
  на macOS CPython 3.11 — 182 Python passed; Node — 429 passed,
  1 Windows-only skipped. Это локальная проверка, не Windows/Linux CI.
- [x] Обязательные CI точного source `5eee97e` и их run/artifact IDs,
  digest, commit/tree сохранены в [qualification](../../releases/core/0.1.0.dev19/qualification.json).
- [x] Принятый Windows CI kit: GitHub artifact digest, ZIP SHA256, provenance,
  offline installation и Companion→installed CLI подтверждены той же квалификацией.
- [x] Canonical Windows wheel сопоставлен с Linux wheel; Linux установленный
  CLI, loopback HTTP/static assets/Rust и браузерные gates проверены по receipts.
- [x] Финальный Linux supplement собран воспроизводимо из принятых байтов;
  проверены архив и установка извлечённого комплекта на Linux.
  [Отдельный ручной gate](../../.github/workflows/release-candidate-ci.yml)
  использует канонический Windows wheel и same-source helper; его реальный
  результат и installed/browser receipts сохранены в qualification.
- [x] Accepted manifests, notes и qualification зафиксированы; release-assets
  подготовлены и проверены штатными scripts/release, без замены исходного ZIP.
- [x] Исторический PR #99 слит обычным merge в `5eee97e`; этот source остаётся
  целью Core tag. Последующий успешный Companion tag workflow и его commit
  сохранены в [отдельной квитанции](evidence/companion-0.1.20-tag-20261015.json).
- [x] Component prerelease опубликованы без перезаписи старых тегов/файлов;
  публичные assets скачаны без авторизации и сверены по всем размерам/SHA256:
  [publication receipt](evidence/release-dev19-publication-20261015.json).
- [x] После подтверждения публикации обновлены исходники README, READINESS,
  GETTING_STARTED и Pages. Это изменение текстов, без заявления deployment.
- [ ] Отдельно принять первый результат нового пользователя и измерить время;
  успешная offline installation не закрывает этот пользовательский gate.

Операционный gate сайта подтверждается успешным Pages workflow для точного
итогового main и проверкой публичного HTTP после слияния; About проверяется
отдельно по фактическим данным GitHub. Описание About и homepage проверены
15 октября 2026 и соответствуют границам продукта. Изменение исходников сайта
не заменяет успешный deployment и отдельную проверку публичного HTTP.

Полный Linux suite имеет известный baseline, а не обещание «все тесты зелёные».
Новые failure IDs запрещены. Точный результат и количество сохраняются в
квалификации кандидата; исторические 90 failures / 2 errors не выдаются за
проверку новой сборки.

## Порядок репозитория

Продуктовый блок кандидата подготовлен в ветке `codex/release-convergence-20261015`.
PR #99 закрыт обычным merge `5eee97ea050c9f4c06eaceb4d191f16868fb0141`;
его точный HEAD `9a7ba6d9df49231ee9b18fb8d2931dda60a7f6d5` сохранён в истории,
завершённая remote-ветка удалена. После этой очистки на remote остались `main`
и отдельная ветка незавершённого draft #84; новые release-record изменения
проходят собственное ревью.
Release-record commit `d5c4022dfaf413581614875c87df7ab679d87102` уже закреплён
публичным тегом `companion-v0.1.20` и сохраняется неизменным. Records,
post-release evidence, документация и политика выпуска собраны в один финальный
блок для squash одним итоговым коммитом. Он сохраняет принятые теги и исходники;
подготовка этого блока не приписывается PR #99. Новый main не становится source принятого Core dev19:
его tag и bytes остаются привязаны к `5eee97ea050c9f4c06eaceb4d191f16868fb0141`.
15 remote-веток завершённых PR удалены после проверки, что их точные HEAD
входят в исходный main; история и merge commits остаются доступны.
Ещё 7 заменённых/диагностических refs сохранены в проверенном Git bundle,
после чего сняты с remote; их код перенесён в main/#84 либо остаётся доступен
в архиве для исследования. Три старых worktree и четыре локальные ветки
убраны после проверки сохранности истории и приватных трасс. Ветка #84
сохранена. Старые незакоммиченные правки основного checkout сохранены в stash
и bundle, затем локальный main обновлён fast-forward без потери работы.
Новые изменения проходят тесты и публикуются с понятным PR и точным scope.

[Правила выпуска](../../scripts/release/README.md) ·
[Текущая поставка](READINESS.md) · [Платформы](PLATFORM-SUPPORT.md)
