# Сверка планов и следующий выпуск

Дата аудита: 15 октября 2026. Исходная база — `main`
`998e19a4e4234737f7d987e1f1737ab8270b34e6` после PR #98.
Опубликована пара Core dev17 / Companion 0.1.18; новый кандидат —
**Core dev19 / Companion 0.1.20**, компонентный prerelease.
Номера dev18 / 0.1.19 уже использованы невыпущенным draft #84.
Ни план, ни изменение версии не являются подтверждением выпуска.

## Что сделано и что остаётся

| Направление / план | Что есть | Что ещё не принято |
| --- | --- | --- |
| [ROADMAP §1: первый результат](../../ROADMAP.md) | Windows маршрут «выгрузка → снимок → модули», инструкции и опубликованный комплект | Повторная установка и сценарий точных новых файлов; измерение времени нового пользователя |
| [IDE, 24 сценария](IDE-DEVELOPMENT-PLAN.md) | Макеты; отдельные GUI-срезы поиска, чтения, сравнения | Все 24 сквозных сценария остаются открытыми; выбор оболочки, storage/search/debug, команды и AI benchmark |
| [Локальная правка](LOCAL-REPAIR-PLAN.md) | Парсер, CLI/MCP, история и UI Companion; ручной черновик и точное редактирование PR #76–#79 | Отрицательная AI-приёмка не стала положительной; реальное качество модели и ежедневная работа требуют новых опытов |
| [Снимки и Observer](SNAPSHOT-OBSERVER-PLAN.md) | Завершённый ограниченный план dev8, чтение/сравнение снимков, installed-smoke в CI | Новые пакеты проходят проверку заново; полная переносимость capture/observer не заявлена |
| [Native-платформа](NATIVE-PLATFORM-PLAN.md) | Исторические опыты на 1С 8.3.27.2342 и собственных фикстурах | Формы, расширенная матрица runtime, произвольные конфигурации, полный rollback и новая native-приёмка |
| [EDT adapter](EDT-ADAPTER-PLAN.md) | Профили, исполнитель, SnapshotRef/materialization, preview и ограниченный native опыт dev13 | Типовые конфигурации, общая матрица объектов и квалификация новой установленной поставки |
| [Узкая диагностика](NARROW-DIAGNOSTICS-PLAN.md) | Синтетический Rust kernel и детерминированные контракты | Независимый benchmark, native probes, пользовательский CLI/MCP-сценарий; синтетика не равна продуктовой диагностике |
| [Portable core](PORTABLE-CORE.md) | Linux local state/history/planners и bounded ZIP CLI выпущены экспериментально | Capture, live apply и native 1С на Linux; полноценная macOS-поддержка |
| [Локальный GUI](LOCAL-GUI.md) | PR #83, #85–#98: импорт, поиск, страницы, реквизиты, вхождения, два/три ZIP, отчёты и ограниченный line diff; Linux checkout CI | Установка финального Linux-комплекта и браузерная приёмка установленного wheel; Windows/macOS GUI |
| [Обновления](THREE-WAY-UPDATES.md) и [семантика](METADATA-THREE-WAY-SEMANTICS.md) | Ограниченные BSL/XML writers, byte/JSON planners, read-only three-ZIP inventory | Общий предок, семантическое слияние, безопасная загрузка в любую базу и сценарии IDE 04/05 |
| [Git watcher](GIT-WATCHER.md), source-facts PR #84 | Watcher/SCM/Git contracts в main; отдельный source-facts draft | В #84: конфликт lifecycle, полный176/whole-process gate, source cohort и installed-wheel; draft не включён в кандидат |
| Производительность и интеграции | Bounded Rust import и ограниченные замеры; прямой Ollama adapter | Репрезентативные cold/warm benchmark, универсальное ускорение, защищённый маршрут Spectorn |

Наличие кода, старого native-отчёта или одного зелёного теста не закрывает
весь ряд таблицы. Исторические evidence сохраняют свои версии и даты.

## Состав кандидата

- Windows x64 / CPython 3.11: локальное ядро, Go scanner и offline kit;
  исправления после dev17, ручное создание/редактирование черновиков,
  проверяемая совместимость Companion 0.1.20.
- GNU/Linux x86_64 / CPython 3.11 и 3.12: экспериментальное дополнение
  с тем же pure-Python wheel и принятым Rust input core. Новый GUI читает
  ограниченные Designer XML ZIP, показывает поиск/сравнение без записи.
- Новая полная IDE, source-facts PR #84, native 1С бизнес-приёмка, качество AI,
  cold OwnerIPC и полный Linux/macOS продукт не заявляются.

## Gates перед публикацией

- [x] Сверить remote main, открытые PR/issues и планы. Открытых issues нет;
  #84 остаётся draft с конфликтом и отдельной квалификацией.
- [x] Разделить кандидат и опубликованные пакеты в README и документации.
- [x] Проверить изменения новой версии и release tooling узкими тестами:
  на macOS CPython 3.11 — 182 Python passed; Node — 429 passed,
  1 Windows-only skipped. Это локальная проверка, не Windows/Linux CI.
- [ ] Получить успешные обязательные CI точного кандидата; сохранить source
  commit/tree, run/artifact IDs и digest без переноса результатов старого HEAD.
- [ ] Скачать Windows CI kit, проверить GitHub artifact digest, ZIP SHA256,
  внутренний provenance, offline installation и Companion→installed CLI.
- [ ] Сверить Windows/Linux pure-Python wheel; проверить Linux установленный
  CLI, loopback HTTP/static assets/Rust и все браузерные gates без skips.
- [ ] Собрать Linux supplement из принятых байтов; повторить сборку,
  проверить архив и установку извлечённого финального комплекта на Linux.
- [ ] Закоммитить manifests, notes и qualification с фактическими результатами;
  сформировать accepted release-assets штатными scripts/release.
- [ ] Слить проверенные изменения обычным merge, сохранив provenance исходных
  сборок; выполнить требуемые main/tag проверки, не подменять принятые ZIP.
- [ ] Опубликовать новые component prerelease без перезаписи старых тегов/файлов;
  скачать публичные assets без авторизации и сверить все размеры/SHA256.
- [ ] Обновить опубликованную пару в README, READINESS, GETTING_STARTED,
  Pages и About только после подтверждения публикации.

Полный Linux suite имеет известный baseline, а не обещание «все тесты зелёные».
Новые failure IDs запрещены. Точный результат и количество сохраняются в
квалификации кандидата; исторические 90 failures / 2 errors не выдаются за
проверку новой сборки.

## Порядок репозитория

Для кандидата используется одна ветка `codex/release-convergence-20261015`.
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
