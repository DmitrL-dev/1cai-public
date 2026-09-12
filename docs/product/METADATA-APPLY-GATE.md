# Квалификация candidate перед будущим metadata apply

Статус: внутренний read-only Python API, схема 1. Этот gate сопоставляет
сохранённый metadata preview с сохранённой квитанцией `native-compile-v1`.
Он не запускает 1С или EDT, не записывает исходники и не разрешает live apply.
Даже результат `passed` содержит `live_apply_allowed=false` и
`live_source_written=false`.

## Вызов и результат

```python
from rentgen_core.metadata_apply_gate import qualify_candidate, require_live_apply

result = qualify_candidate(
    ctx,
    preview_operation_id,
    platform_operation_id,
    expected_preview_id=preview_id,
    expected_platform_executable_sha256=platform_sha256,
)
assert result["live_apply_allowed"] is False
```

Вход содержит только два канонических UUID сохранённых операций, точный
`preview_id` и ожидаемый SHA256 EXE. JSON preview, report, произвольный путь,
строка «проверено», статус пользователя или текст лога не являются входом API.
Контекст и текущий пользователь поступают от доверенного локального адаптера.

`qualify_candidate` возвращает наблюдение, а не записывает новую квитанцию на
диск. Повторный вызов заново читает свидетельства и проверяет права. Совпавшие
входы и неизменившиеся свидетельства дают одинаковый `qualification_id` — SHA256
канонического результата без самого поля `qualification_id`. Этот хэш не является
подписью или capability на запись.

`require_live_apply` принимает те же аргументы, заново выполняет квалификацию
и всегда завершает вызов ошибкой `METADATA_LIVE_APPLY_UNAVAILABLE` после
успешного чтения. Некорректные данные и отказ доступа возвращают свою ошибку
раньше. Функция не принимает прежний результат gate как разрешение.

## Проверяемые привязки

- `get_preview` повторно строит preview из retained input/baseline/candidate,
  проверяет план, UUID объектов, hash и закрытие EDT runtime. Gate сопоставляет
  результат с ожидаемым `preview_id`; дополнительные business evidence не
  предоставляют разрешение apply.
- `get_platform_run` читает только namespace `platform-checks`, проверяет проект,
  UUID операции, SHA256 report и согласованность request/report. Gate дополнительно
  требует полный request и точную схему версии 1, профиль `native-compile-v1`,
  политику `native-resources-v1`, provenance автора и timestamp с часовым поясом.
- Snapshot и layer в `source_ref` должны точно совпадать с preview. SHA256 EXE
  в request/report должен совпадать с ожидаемым. Locator EXE проверяется по
  форме, но EXE не открывается и его текущая доступность не требуется.
- SHA256 **полных** baseline и candidate inventories должны совпасть с preview.
  Gate повторно читает соответствующие retained деревья platform-check,
  включая неизвестные файлы, и сверяет их с inventory. Совпадения хэша одного
  BSL-модуля недостаточно. Original inventory также входит в binding результата.
- Для completed report требуются ровно семь шагов create/load/dump/check в
  установленном порядке и все четыре контекста текущего `NativePlatform`.
  Exit code проверяется как целое число, `bool` не принимается. `passed`/diagnostics
  должны совпасть с кодом 0/101 шага check; остальные шаги требуют 0.
- SHA256 retained log/stdout/stderr каждого шага проверяется по байтам. Текст
  лога должен совпасть с записанным. Он остаётся данными, не попадает в решение
  и не интерпретируется как инструкция или сигнал успеха. Проверяются также
  hash и текст roundtrip выбранного BSL-модуля, как в native-compile-v1.

В результате сохраняются project/preview/platform operation IDs, preview/plan/
EDT-profile IDs, snapshot/layer, три inventory hashes и EXE hash. Provenance
содержит SHA256 request, report либо failure, `evidence=local_unattested`,
`scope=native-compile-v1`, `runtime_dependencies=not_fully_pinned`.

## Исходы и отказ

| `status` | Значение |
|---|---|
| `passed` | Завершённая согласованная локальная квитанция сообщает успешную компиляцию baseline и candidate. |
| `diagnostics` | Завершённая согласованная квитанция содержит код 101 хотя бы для одной фазы. |
| `timeout` | Есть согласованный request и terminal failure с кодом `PLATFORM_TIMEOUT`; completed report отсутствует. |
| `failed` | Есть согласованный request и другое terminal failure; completed report отсутствует. |
| `incomplete` | Есть согласованный request, terminal report/failure отсутствуют. Это не утверждает, что процесс ещё работает. |

Для timeout/failed/incomplete `report_sha256=null`; никакое из этих состояний
не квалифицирует candidate как успешно скомпилированный. Failure details
остаются ограниченным по размеру непрозрачным diagnostic DTO: хэшируются для
provenance, но не копируются и не влияют на разрешение записи. Их `run_id`
обязательно совпадает с операцией.

Отсутствующий request, лишние поля протокола, несовместимая схема или одновременно
report и failure вызывают отказ. Иной preview/snapshot/layer/EXE/inventory
вызывает `METADATA_GATE_CONFLICT`; собственная проверка DTO —
`METADATA_GATE_INVALID`. Существующие readers сохраняют свои коды ошибок для
повреждённых или незавершённых входов. Незнакомое состояние никогда не становится
успехом. Операция не перезапускается, records не перезаписываются.

## Права, границы размера и конкурентные изменения

Текущие `project:read`, `source:edit`, `analysis:run` проверяются до разбора
аргументов, между чтениями, при обходе файлов и перед возвратом; внешний
authorization context проверяет права также при исключении. `requested_by`
в квитанции — provenance исторического вызова, не текущая авторизация.

Сохранённый preview ограничен существующим reader до 2 MiB, каждый native
record — до 1.5 MiB с запретом повторных JSON ключей. Gate принимает inventory
до 8192 файлов, 64 MiB на файл и 256 MiB суммарно; проверяет точные ключи строк,
тип размера, SHA256 в нижнем регистре, порядок и отсутствие опасных/конфликтующих
путей. Существующий filesystem inventory scanner имеет собственный предел
8192 файлов, 256 MiB на файл и 4 GiB на дерево; результат обхода всё равно
должен точно совпасть с более узким inventory gate. Каждый поток вывода
ограничен 128 KiB, BSL roundtrip — 2 MiB.

Используются Windows no-follow/pinning readers. Известные input-файлы удерживаются
при проверке, полные inventories и записи повторно читаются для обнаружения
изменений. Это наблюдение retained evidence, а не блокировка внешнего workspace
на весь будущий apply. Gate не проверяет актуальность живых файлов или head;
их повторная проверка остаётся обязанностью writer/preflight.

## Что этот срез не доказывает

Текущий producer `check_proposal_platform_json` создаёт квитанцию для изменения
одного BSL-модуля. Он не принимает metadata preview и не умеет скомпилировать
произвольное metadata rename как собственную операцию. Обычная квитанция BSL
proposal не пройдёт gate, если её полные baseline/candidate inventories
отличаются от preview. Переименование UUID/operation, перепривязка snapshot
или замена inventory ради совпадения не являются допустимым способом интеграции.

Положительные unit-тесты используют явно синтетические сохранённые квитанции.
Они доказывают контракт сопоставления, а не реальный запуск 1С. Этот срез не
добавляет producer metadata platform-check и не закрывает цепочку
preview → apply → re-read → undo.

Даже корректная квитанция не является аттестацией: тот же пользователь ОС
может переписать данные и пересчитать хэши. EXE hash не покрывает все runtime
зависимости. Roundtrip выбранного BSL не доказывает сохранность всех UUID,
нормализации EDT, бизнес-данных, форм или семантики всей конфигурации.
Нормализация остаётся `normalization_not_qualified`; write/recovery protocol
отсутствует. Нужны отдельный producer для точного metadata candidate, полная
квалификация преобразования, рабочая копия операции, журнал многокомпонентной
записи и восстановления и собственная квитанция apply с проверкой чужих правок.

Этот API не интегрирован в CLI/MCP/editor и не меняет
[METADATA-APPLY.md](METADATA-APPLY.md) или реализацию существующего preflight.
