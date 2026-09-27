# Локальная причина отказа Git BSL: план реализации

> **Актуальное указание владельца от 27 сентября:** субагентов не использовать. Дальнейшую реализацию, сбор доказательств и итоговую проверку выполняет основной агент. Ранее полученное независимое ревью сохраняется в протоколе.

**Goal:** после отказа обычного установленного GitAuditWorker сохранить проверенную BSL-причину только в локальном fatal journal.

**Architecture:** внутренний `GitAnalysisFailure(CoreError)` переносит ограниченный код причины от BSL Git adapter до scheduler. Adapter проверяет точный DTO, привязку и авторизацию после ответа. Scheduler повторно проверяет точный тип ошибки и allowlist; outbox и транспортный `to_dict()` сохраняют прежний формат.

**Tech Stack:** Python 3.11, pytest, существующие Windows CLI, SchedulerJournal, Core kit и Product checks.

## Общие ограничения

- Основа: [спецификация](../specs/2026-09-27-git-bsl-failure-reason-design.md), head до реализации `a4aa57633b58965eca12839801ce9edb0a310869`.
- 15 кодов из спецификации и ровно один суффикс `_CLEANUP_FAILED`; произвольные строки, paths, stdout/stderr и details в журнал не копируются.
- Дополнительный объект: `analysis_failure = {"schema": 1, "reason": reason}` только для fatal `GIT_ANALYZER_INCOMPLETE`.
- Поведение retries, cleanup/quarantine, целостность runtime, критерии успешных findings и owner report сохраняются.
- Новый запуск заменяет предыдущую запись журнала. Этот журнал не является архивом.
- Продолжение локального среза входит в действующее поручение владельца. Отдельное одобрение именно текста дизайна не заявляется. Production deployment требует отдельного разрешения.

## 1. Передача проверенной причины

**Файлы:** создать `rentgen_core/_git_analysis_failure.py`; изменить `rentgen_diagnostics/git_bsl_analyzer.py`, `rentgen_core/git_watcher.py`; тесты в `tests/unit/test_git_bsl_analyzer.py`, `tests/unit/test_git_watcher.py`, `tests/unit/test_service_composition.py`.

- [x] Сначала добавить тесты: валидные failed/unsupported DTO передают известную причину; подмена hash/size/profile/manifest/config, неверный тип DTO/статуса/reason, неизвестные и опасные строки её не передают; отзыв авторизации после adapter имеет приоритет.
- [x] Выполнить новый положительный тест причины до реализации: ожидается отсутствие атрибута/значения причины у прежнего `CoreError`.
- [x] Ввести внутренний тип с прежними `code="GIT_ANALYZER_INCOMPLETE"`, `message="BSL-LS result is not bound to the committed blob"`, пустыми `details` и отдельным `reason`. Проверка причины использует точный `str` и конечный `frozenset`.
- [x] После `adapter.analyze` вызвать `self.authorize()`. Обогащать только точный `BslAnalysis` со статусом `failed`/`unsupported`, для которого `_analysis_valid(analysis, raw)` истинен и причина входит в allowlist. Иначе выбрасывать прежний общий `CoreError`.
- [x] На fatal-ветке scheduler сформировать локальное событие через helper `local_failure_event(error)`: общий status/code всегда, причина только для точного `GitAnalysisFailure`, прежнего code и повторно разрешённой причины. В outbox передавать прежний отдельный словарь status/code.
- [x] Проверить границы: транспортная сериализация без причины, поддельные CoreError/details и подклассы не обогащают journal, изменённые атрибуты повторно проверяются, ошибка journal сохраняет первичное исключение, следующий запуск удаляет старую причину.
- [x] Выполнить узкую регрессию трёх файлов и отдельный процесс с управляемым adapter; это проверка контракта, не репродукция runtime-дефекта.

Команда узкой регрессии (из корня репозитория, Python из приватного test-env):

```powershell
python -m pytest -q --tb=short -p no:cacheprovider tests/unit/test_git_bsl_analyzer.py tests/unit/test_git_watcher.py tests/unit/test_service_composition.py --junitxml=output/git-failure-focused.xml
```

## 2. Кандидат и установленная проверка

- [x] Подготовить Core `0.1.0.dev12`, обновить совместимость runtime installer и необходимые release contracts; dev11 assets сохраняются.
- [x] Построить kit существующим release workflow, проверить offline install, CLI/MCP, snapshot/observer contracts на точном коммите. Проверить реальную область покрытия verifier и SHA256 скачанных артефактов.
- [x] В собственной свежей установке выполнить обычный service CLI без probe/monkeypatch; сохранить commit/snapshot, exit, journal/outbox, owner reports и чистоту исходников.
- [x] В отдельной своей установке изменить только первый байт JAR, сохранив размер; обычный CLI обязан дать общий `SERVICE_WORKER_FAILED`, outbox fatal `GIT_ANALYZER_INCOMPLETE`, отсутствие успешного отчёта и journal reason точно `BSL_RUNTIME_MISMATCH`.
- [x] Не считать три успешные диагностические установки 27.09 доказательством исправления исходного `BSL_INPUT_CHANGED`; issue #23 остаётся открытым.

## 3. Ревью, поставка, checkpoint

- [x] Независимое ревью реализации, совместимости и отрицательного native-контракта выполнено; замечания к полноте проверки закрыты дополнительным аудитом. Успешный native-сценарий и дальнейшую квалификацию проверяет основной агент по актуальному указанию владельца.
- [x] Обновить `docs/product/READINESS.md`, документацию service journal и подробный протокол установленного кандидата с компактной квитанцией.
- [x] Обновить PR #32 фактическим изменением и проверками, дождаться Product checks на итоговом head, проверить точный checkout и артефакты.
- [x] Принятый срез довести до public main и проверить postmerge CI.
- [x] Опубликовать новый prerelease с подробным описанием, неизменяемыми артефактами и хэшами; обновить issue #23 и checkpoint. Полную готовность продукта и устранение старой перемежающейся ошибки не заявлять без соответствующих доказательств.

## Фактический checkpoint 27 сентября

Реализация и совместимость закоммичены в `659a3ae` / `a35711c`. Локально:
141 диагностический тест, 47 тестов совместимости и поставки, 63 Node-контракта,
38 тестов live apply/recovery. Две сборки, offline CLI/MCP, snapshot и observer
прошли. [Native-протокол](../../product/SERVICE-GIT-FAILURE-REASON-DEV12.md)
сохраняет также неудачный первый installer; следующие negative и healthy
сценарии не закрывают холодную надёжность.

Независимое ревью кода, совместимости и отрицательного native-контракта
выполнено. После указания владельца не использовать субагентов дальнейшую
проверку, включая healthy native evidence и релиз, выполняет основной агент.
Исходный коммит прошёл оба CI: по 2389 Python-тестов, 63 Node-контракта,
Go и установленные проверки. Принят push CI ZIP; его отдельная офлайн-установка
прошла. Оба CI итогового коммита `14c6580` и проверка объединённого main
`3536185` завершены. Core dev12 и Companion 0.1.12 опубликованы; все семь
публичных файлов скачаны без авторизации и сверены.
[Квитанция публикации](../../product/evidence/release-dev12-publication-20260927.json)
сохраняет фактические теги, workflow, хэши и ссылку на подробный анонс.
Общая продуктовая готовность не заявляется; issue #23 и #25 открыты.
