# Изменения файлов между снимками

## Контракт SNAP-DIFF-01

Сравнение двух явных retained snapshots возвращает добавленные, удалённые
и изменённые файлы, точные SourceRef и общие количества. Идентичность — слой,
точный путь и SHA-256 исходных байтов. Переименование считается удалением
и добавлением; семантическая идентичность и качество кода из этого не выводятся.
Текущий source tree, scanner и модель для чтения сохранённой пары не нужны.

Linux CLI/MCP-маршрут реализован в development-исходниках SNAP-DIFF-01.
Он не обновляет опубликованные Core dev19 / Companion 0.1.20. Поддержка
конкретного source/build-кандидата определяется отдельной проверенной
[квитанцией точных source и bytes](#приёмка-конкретной-сборки).
CI более раннего main `8e7346e` этот новый блок не проверял.
[Первый CI `597e50e`](evidence/development-ci-597e50e-20261016.json)
сохраняет Linux tool-catalog oracle failure до capture и Windows installed-workflow
failure с неизвестной внутренней причиной. Installed pair этого HEAD не принят;
исправленные проверяющие клиенты требуют собственной новой приёмки.

## CLI и MCP

После двух публикаций в одном доступном проекте, из окружения выбранной сборки:

```sh
rentgen snapshot-diff --registry ./registry.sqlite3 \
  --identity-profile ./account/identity.json --project PROJECT_UUID \
  --before BEFORE_SHA256 --after AFTER_SHA256 --limit 100
```

Новый MCP tool — `rentgen_snapshot_diff`. Обязательны `project_id`,
`before_snapshot_id` и `after_snapshot_id`; необязательны `limit`
(целое 1–100, default 100) и `cursor`. Registry, identity profile и scanner —
trusted startup configuration сервера, а не аргументы tool. Бюджеты операции
не принимаются из CLI/MCP-запроса.

```json
{
  "name": "rentgen_snapshot_diff",
  "arguments": {
    "project_id": "PROJECT_UUID",
    "before_snapshot_id": "BEFORE_SHA256",
    "after_snapshot_id": "AFTER_SHA256",
    "limit": 100
  }
}
```

`counts` относится ко всей паре, `changes` — к текущей странице.
Строка содержит `kind` и `before`/`after` с точными SourceRef; отсутствующая
сторона — `null`. `next_cursor=null` означает последнюю страницу. Следующий
вызов сохраняет порядок снимков, project и limit и добавляет `cursor`.
Курсор не выдаёт права и не выбирает новый head. Каждая страница заново
проверяет пару и retained bytes, без продолжения живой read session.

## Лимиты одного сравнения

Linux создаёт общий operation owner до первого registry/state/catalog lookup,
без двух предварительных eager resolver проходов. Обе стороны, retained
manifest/source/graph проверки, индексы и выдача ответа используют один исходный
deadline. Более узкие session/graph limits действуют дополнительно.

| Общий default | Что учитывается |
| --- | --- |
| 512 МиБ bounded read allowance | Разрешённые bounded reads обеих сторон, включая grow/probe byte и повторные проверки; это не только фактически возвращённые source bytes |
| 8 ГиБ image accounting | Одновременно удерживаемые консервативные envelopes manifest/source/graph, индексов и временных представлений; **не измеренный RAM и не hard RSS cap** |
| 40 000 source entries | Совокупный source entry allowance обеих сторон |
| 1 200 000 inventory items | Совокупная работа проверки inventory |
| 128 МиБ graph row allowance | Консервативные reservations/precharges строк graph SQLite, не счётчик фактически прочитанных строк |
| 20 000 000 graph VM allowance | Консервативные reservations/precharges VM graph SQLite; state/catalog SQLite сюда не входят |
| 8192 descriptors / 32 cursors | Совместно удерживаемые descriptor/cursor reservations |
| 30 секунд | Один исходный monotonic deadline, без сброса на второй стороне, сериализации или final authorization |

Накопленная работа не возвращается в бюджет после закрытия первой стороны.
Удерживаемые reservations освобождаются после подтверждённого cleanup владельца.
Индексы и сортировка всей пары получают консервативный precharge до выделения,
а сохраняются только строки текущей страницы. Deadline проверяется кооперативно
и не обещает жёсткое прерывание блокирующего syscall.
Область resource accounting — retained POSIX/graph envelopes: это не общий
лимит процесса, RSS, всех SQLite-запросов или физического disk IO.

JSON страницы ограничен 1 МиБ. Linux CLI ограничивает полный output envelope
2 МиБ, включая request ID и newline. Для нового MCP tool предел 2 МиБ относится
к **полному emitted wire response**: JSON-RPC ID, newline, emitted metadata и двум JSON
представлениям — text content и structuredContent. Поэтому страница, прошедшая
предел 1 МиБ, может не поместиться в MCP envelope. Ответ отклоняется с
`OUTPUT_LIMIT_EXCEEDED` / `DIFF_PAGE_LIMIT`; уменьшите limit.
Успешный ответ не обрезается. Private authorization scope удаляется перед
выдачей; его bytes не считаются частью emitted wire.

Оба read owner должны успешно выйти до раскрытия результата. Затем заново
проверяются project permission, точная ordered catalog pair и исходный deadline.
MCP проверяет оба полных одинаковых JSON представления, request ID, pair/metadata
binding и полный SDK wire. Потеря представления, изменённая metadata,
duplicate JSON keys или неверный response ID не превращаются в успех.

## Границы платформ

- GNU/Linux amd64: отдельный read-only маршрут для сохранённой пары private
  project/default-base source+graph; shared accounting описан выше.
  Metadata/drafts/native/live apply и весь B07 этим не открываются.
- Windows CLI существует с dev8 и сохраняет прежний per-session ресурсный
  контракт. Новый Windows MCP использует pair coordinator с общим deadline
  и final output guard, сохраняя прежние per-session ceilings.
  POSIX shared resource accounting на Windows не заявляется.
- Публичные CLI/MCP entrypoints macOS по-прежнему отказывают.
  Внутренняя POSIX fixture на macOS не является поддержкой продукта.

Это не Observer-служба, semantic merge, rename inference, native 1С/EDT,
human GUI или модельная приёмка. Будущий observer сначала проверяет snapshot ID
и не повторяет дорогое сравнение при неизменившемся head.

## Приёмка конкретной сборки

Source implementation, локальные controls и CI предыдущего main не заменяют
actual Linux и installed CLI/официальный SDK. Проверяемая запись связывает:

- финальные source SHA/tree и synthetic checkout parents, если это PR;
- оригинальный GitHub artifact size/digest **до** bounded extraction, final
  archive/manifest, Core/graph/interface wheels, scanner и SDK lock;
- actual installed CLI/официальный SDK: explicit pair, exact counts, страницы,
  history после более позднего head без текущих source/scanner, а также отдельные
  protocol outcomes для unknown pair, cursor mismatch, tamper и revocation;
- отдельные trusted installed-library controls: low combined budget, early
  cancellation, original deadline и final scope/permission checks. Их параметры
  не являются public CLI/MCP knobs, а отказ SDK сам по себе не доказывает
  cancellation во время копирования;
- отдельные local wire controls: oversized response, lost/unequal JSON
  representations, duplicate keys, request ID и scope/metadata mutation;
- для каждой группы — точные executed/skipped/refused counts, accounting,
  оба owner exits/cleanup и неизменность state/head/source/receipts.

[Контракт offline-комплекта](../../scripts/release/OWNED-LINUX-KIT.md#qualification-still-required)
сохраняет build manifest как candidate после положительной отдельной
acceptance.json. Датированная квитанция относится только к своим source/bytes
и scope. Она не закрывает 127 требований, 24 IDE-сценария или финальный релиз.
