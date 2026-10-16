# Проверка сохранённых результатов YAxUnit

Статус: блок `TEST-RUN-QUAL-01` реализован в development-исходниках после main
`2d8254a75f4d12e794a0e6597a5d4671aeba0564`. Exact-source CI новой сборки
обязателен отдельно; опубликованные Core dev19 / Companion 0.1.20 эту команду
не содержат. Документ не закрывает `TEST-PROFILE-01`, `TEST-YAXUNIT-01`,
`IDE-SC-20`, `DAILY-NATIVE-01` или какой-либо полный IDE/native/release gate из
[реестра](FULL-FINAL-PLAN.md).

## Что делает чтение

`proposal-test` сохраняет в `test-runs/<operation UUID>` request/report,
материализованные `baseline/` и `candidate/`, native roundtrip, журналы шагов,
settings, JUnit и exit-файлы. Прежнее историческое чтение `proposal-test-result`
сверяет только request/report bindings и хэш отчёта.

Новое чтение повторно сверяет сохранённые raw artifacts с отчётом и возвращает
ограниченное досье. Оно не запускает 1С, не повторяет операцию, не применяет
предложение и не открывает рабочую ИБ, live source, снимок или исполняемый файл.
Результат тестов (заявление отчёта) и полнота доказательств показаны отдельно.

```sh
rentgen test-run-qualify --registry ./registry.sqlite3 \
  --project PROJECT_UUID --operation-id OPERATION_UUID
```

Нужны права `project:read`, `source:edit`, `analysis:run`; они проверяются до,
во время обхода каждого каталога и после чтения. Отключённый профиль не мешает
квалифицировать прежний запуск: досье показывает `profile.enabled:false`.
Команда относится к отдельной capability-группе `native.evidence.read` и
поддерживается только адаптером Windows. На Linux/macOS она отказывает
`CAPABILITY_UNAVAILABLE` до чтения. MCP tool не добавлен.

## Досье

Поля: `run_id`, `project_id`, `run_status` (`completed` / `failed` /
`incomplete`), `failure_code`, `binding`, `profile`, `candidate_sha256`,
`report_sha256`, `test_result` (заявленные статусы отчёта), `qualification`,
упорядоченные `checks`, `evidence:"local_unattested"`, `execution:"not_performed"`,
`apply.status:"unavailable"`, `limitations` и `dossier_sha256`.

`qualification` выводится из проверок: любой `mismatch` — `inconsistent`,
иначе любой `missing` — `incomplete`, иначе `consistent`. Технический сбой или
незавершённый запуск дают `incomplete` и `not_applicable` для всех проверок,
без повторного запуска. Отсутствующие raw artifacts никогда не дают `verified`.

| Проверка | Что сверяется |
| --- | --- |
| `report_identity` | Закрытый набор полей отчёта, `report_sha256`, binding request/report, project, синтаксис пути модуля, `local_unattested` и `apply:unavailable` |
| `profile_definition` | Сохранённое определение профиля и content address, project, platform SHA256 binding, хэш сохранённого `engine.cfe` |
| `input_inventories` | Полные inventory `baseline/` и `candidate/` против digests отчёта; различается только заявленный модуль; candidate SHA256; лишние каталоги запрещены |
| `native_roundtrip` | SHA256 dump-модуля каждой фазы и нормализованное UTF-8 сравнение с материализованным модулем |
| `step_sequence` | Закрытый порядок шагов обеих фаз, допустимые exit codes (compile 0 или 101), хэши и текст log/stdout/stderr; лишние следы недостигнутых шагов |
| `runner_settings` | Байт-в-байт канонические settings: модули профиля, jUnit, точные пути report/exit этого запуска, bool-флаги |
| `junit_exit` | Повторный `yaxunit_report.parse_report` по профилю; все cases/counts/status/digests/exit и client exit; bool не заменяет integer |
| `engine_source` | Digest дерева `engine-with-tests` и байты каждого тестового модуля профиля |
| `scratch_cleanup` | Заявленный cleanup против наличия ibcmd scratch |

Тела журналов, исходного кода и абсолютные пути evidence в досье не выводятся.
Detail — только фиксированный код (`CANDIDATE_JUNIT_STATUS`, `PROFILE_ABSENT` и т.п.).

## Ограничения чтения

Пути берутся только из закрытого набора имён runner и из провалидированного
относительного пути модуля, который должен присутствовать в inventory; пути из
JSON не исполняются и не читаются. Обход `baseline/`, `candidate/` и
`engine-with-tests/` идёт через no-follow handles: reparse point, hardlink,
special object и смена identity делают соответствующую проверку `mismatch`;
изменение уже прочитанных байтов до конца чтения даёт отказ
`TEST_RUN_EVIDENCE_CHANGED`. Pins удерживаются до выдачи результата.

Общий бюджет задаётся типизированными `QualificationLimits`, а не запросом:
60 000 entries, 768 MiB хэшируемых tree bytes, 32 MiB точечных evidence-файлов,
65 536 handles и 300 секунд. Превышение даёт `TEST_RUN_QUALIFY_LIMIT` или
`TEST_RUN_QUALIFY_TIMEOUT`. Это учёт, а не жёсткий лимит RSS.

Если state root перенесён после запуска, точные пути в settings не совпадут, и
`runner_settings` честно покажет `mismatch`.

## Companion

Команда «Рентген: проверить сохранённый запуск тестов» (`rentgen.testQualify`)
доступна, когда Core объявляет операцию `test-run-qualify` в
`native.evidence.read`; список прежних версий Core её не включает и не выключает.
Досье привязано к сохранённому намерению запуска: draft ID, ревизия, SourceRef,
proposal content ID, candidate SHA256, profile ID и operation UUID. При вызове
из выбранной версии черновика несовпадение ревизии отказывает до чтения Core,
а смена выбора, отзыв trust или прав скрывают устаревший результат.

## Проверки и границы

Чистые контроли (`tests/unit/test_test_run_qualification.py`) проверяют
evaluator на явно сконструированных байтах в точном формате runner: исходы
passed/failed/skip-only/`not_run`, подмену JUnit/exit/settings/inventory/
roundtrip/шагов/engine/cleanup, bool вместо integer, отсутствие артефактов и
незавершённые запуски. Windows-тесты
(`tests/unit/test_test_run_qualification_windows.py`) используют настоящий
retained state, pins, hardlink/junction, отзыв прав посреди чтения, лимиты и CLI;
заменён только native runner. Companion покрыт `test/test-qualify.test.cjs`.

Это не native-приёмка: согласованный набор локальных файлов не аутентифицирует
факт исполнения платформой и не даёт права apply. Новое исполнение настоящих
pass/fail/crash/timeout/no-tests на закреплённой 1С/YAxUnit и собственных базах
остаётся обязательным отдельным gate. Лицензированного стенда пока нет; этот
gate ведётся в backlog и обычный CI его не заменяет.
