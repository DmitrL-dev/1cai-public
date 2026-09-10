# Metadata из опубликованного снимка

Первый reader `designer_xml_v1` читает Designer XML из одного pinned
`ProjectContext`. Живой source root, cwd, environment, default configuration,
legacy `metadata_graph` и кэш не используются. Модуль зависит только от stdlib
и `rentgen_core`. HTTP/stdio composition и перевод остальных enrichers имеют
отдельную приёмку.

## API

```python
from rentgen_core.metadata import (
    MetadataLimits, metadata_summary, search_metadata, get_metadata_object,
)

summary = metadata_summary(ctx, layer_id=None)
matches = search_metadata(
    ctx, "Заказ", metadata_type="Document", layer_id=None, limit=30,
)
detail = get_metadata_object(
    ctx, layer_id="base", relative_path="Documents/Заказ.xml",
)
```

`ctx` должен содержать опубликованный `SnapshotRef` и source capability,
полученные от resolver. Каждый use case проверяет `project:read` до inventory,
читает **исторические** слои через `tx.get_snapshot_layers(ctx.snapshot.snapshot_id)`
и ещё раз проверяет доступ перед возвратом. Каждое чтение capability самостоятельно
повторяет актуальную авторизацию. Смена текущей source configuration не изменяет
дескрипторы старого снимка. Ошибка авторизации проходит без добавления source paths.

Единственный ключ object — пара `layer_id` и полного `relative_path`.
Имя, текст UUID, `Type.Name`, basename и путь другого слоя не служат aliases.
Одинаковые XML UUID/имена/пути в base и упорядоченных extensions остаются
разными объектами. `observed_uuid` имеет статус `unverified`; canonical identity
не вычисляется и не подтверждается. Строковые XML references остаются `unresolved`.

Результаты — JSON-compatible dictionaries. Общие поля:

| Поле | Смысл |
|---|---|
| `snapshot` | Полный exact SnapshotRef: project, snapshot, manifest hash |
| `parser` | `designer_xml_v1` |
| `identity_status` | `source_path_only` |
| `layers` | Исторические descriptors в порядке ordinal; явные status/completeness/format decision |
| `evidence_schema` | `metadata_scan_v2`: явная версия представления evidence |
| `source_refs_scope` | `returned_values_and_format_witnesses` |
| `source_refs` | Проверенные refs возвращаемых значений и ограниченных format witnesses; не перечень всех просмотренных файлов |
| `validation_summary` | Отдельные сведения о полной проверке generation и фактическом metadata scan |
| `truncated` | Результат содержит ограниченные коллекции; полные totals отдельно |
| `completeness` | Область покрытия, а не обещание полной семантики 1С |

## Формат и полнота

`source_format="unknown"` не превращается автоматически в Designer XML.
Поддержка определяется по совокупности **пути и прочитанного XML root**:
`Configuration.xml` или известный metadata folder с `Name.xml` / `Name/Name.xml`,
корень `MetaDataObject`, единственный тип объекта, совпадающий с типом пути,
и дочерний `Properties`. Namespace обрабатывается по local names, как в ранее
существовавших чистых extraction utilities. Это распознавание структуры для
ограниченного reader, не XML Schema validation и не доказательство происхождения
выгрузки. `format_decision.evidence` содержит не более трёх проверенных SourceRefs: первый Configuration, первый валидный объект и первое несовпадение root/type, если они встретились. Для EDT это первый проверенный `.mdo`. Поле `evidence_scope="bounded_witnesses"` обозначает примеры, а не полный перечень доказательств.

Явно объявленный EDT слой или наличие `.mdo` даёт `unsupported`, даже если рядом
есть похожий Designer XML. `.mdo` может быть прочитан как opaque bytes для
проверки evidence ref, но EDT parser здесь отсутствует. Отсутствие подтверждающего
XML и несовпадение ожидаемого типа/root тоже дают явное `unsupported`.
Malformed XML, DTD и resource-limit failures завершают вызов ошибкой.

Summary возвращает для каждого слоя:

- `status`: `supported` / `unsupported`;
- `completeness`: `supported_layer_inventory` / `unsupported_format`;
- `format_decision`: declared/detected/status/reason/evidence;
- `inventory_counts`: files, objects, modules, forms, commands, rights_documents;
- `count_basis`: подсчёт путей verified manifest; object roots проверены только
  для поддерживаемого слоя;
- `by_type` и configuration preview для поддерживаемого слоя;
- `parsed_rights=None`: права не разобраны в summary, это не ноль разрешений.

`objects=None` у неподдерживаемого слоя. В остальных inventory counters измеряется
число путей, а не их семантика. Файлы вне поддерживаемого path vocabulary остаются
в числе files, но не объявляются разобранными объектами. Вложенные формы и права
не разобраны в summary. Число modules относится к captured `.bsl/.os/.bsp` путям,
а не к числу процедур или успешных runtime-модулей.

Search добавляет `objects`, `total_matches`, `returned`. Поиск substring без
учёта регистра проходит по имени, synonym, типу и полному пути. `metadata_type`
сравнивается с английским типом без учёта регистра. `limit` — 1..200, строки —
не длиннее 256 символов. Total относится только к полностью просмотренным
поддерживаемым слоям. Неподдерживаемые слои сохраняются в `layers`; общий
`completeness="unsupported_layers"` не позволяет выдать частичное покрытие за полное.
`truncated` отдельно показывает ограничение списка matches.

## Вложенные сведения объекта

Object добавляет `object` с source_ref/type/name/synonym/observed_uuid и:

- `properties`: leaf projection XML Properties с сохранёнными строками,
  путями вложенности и XML attributes;
- attributes/tabular_sections/dimensions/resources, включая вложенные Properties;
- строковые references с `resolution="unresolved"`;
- forms и commands из той же директории объекта и того же слоя;
- form_documents (`Forms/.../Ext/Form.xml` и собственный `CommonForms/Name/Ext/Form.xml`)
  с bounded leaf fields;
- modules с проверенным SourceRef, raw size, encoding metadata и
  `status="verified_bytes"`; BSL здесь не декодируется и не переписывается;
- rights из `Ext/Rights.xml`, если он присутствует в этом снимке.

Коллекции имеют `items`, `total`, `truncated`. В XML-коллекциях total считается
по полностью разобранному bounded дереву. У assets total — inventory count;
прочитаны только возвращаемые первые items, остальные не получают SourceRefs в
результате. Общий `truncated` учитывает вложенные коллекции. XML projection не
заменяет весь исходный документ: будущий enricher читает полный raw XML по
SourceRef через **тот же** `ctx.sources`, повторяя авторизацию и hash verification.

Rights сообщает количество XML объектов, объявленных rights и явно enabled
true/false. Неизвестное/отсутствующее boolean значение или имя даёт
`status="uninterpreted_values"`, `enabled_rights=None`. Отсутствие файла даёт
`status="absent_in_snapshot"`, `counts=None`; malformed/неподдерживаемый root
не превращается в нулевые counts. Даже `status="parsed"` означает только
прочитанные XML declarations: effective platform permissions, RLS, опасность
действий и безопасность конфигурации не доказаны.

## Пределы и ошибки

`MetadataLimits` позволяет только уменьшать следующие hard maxima:

| Опция | По умолчанию / максимум |
|---|---|
| `max_xml_bytes` | 4 MiB на XML |
| `max_nodes` | 50 000 XML nodes на документ |
| `max_depth` | 64 |
| `max_inventory` | 20 000 source entries |
| `max_collection` | 200 items |
| `max_total_bytes` | 64 MiB raw source bytes за use case |
| `max_asset_bytes` | 16 MiB на непрозрачный asset/module |

Manifest size проверяется до открытия source bytes. XMLParser получает исходные
bytes и учитывает encoding declaration; UTF-8, UTF-16 LE/BE и CP1251 проверены
тестами. DTD отвергается callback `TreeBuilder.doctype` после распознавания
encoding, до обработки declarations. Пользовательские и внешние entities не
разрешены; стандартные XML escapes (`&amp;` и т.п.) остаются обычным XML.
Bytes/node/depth превышение и malformed XML имеют явные ошибки. Нет
`errors="ignore"`, fetch внешних документов или parse-error-to-empty recovery.

Коды: `CONTEXT_REQUIRED`, `SNAPSHOT_REQUIRED`, `PROJECT_FORBIDDEN`,
`SOURCE_LAYER_NOT_FOUND`, `SOURCE_PATH_UNSAFE`, `METADATA_OBJECT_NOT_FOUND`,
`METADATA_FORMAT_UNSUPPORTED`, `XML_FORBIDDEN`, `XML_INVALID`,
`METADATA_LIMIT_EXCEEDED`, `INVALID_QUERY_OPTIONS`. Ошибки повреждённого снимка
сохраняют исходные core-коды. При превышении inventory/byte limit totals не
выдаются. Ошибки конкретного XML включают его SourceRef, ошибки авторизации — нет.

Лимит raw source bytes относится к содержимому, запрошенному metadata reader.
Он отделён от полного raw hash verification generation и работы resolver. Одна
операция использует [сессию чтения](SNAPSHOT-READ-SESSIONS.md): manifest разбирается
один раз, полный inventory проверяется на входе и выходе, expected files остаются
под удерживаемыми handles. Точные search totals требуют полного metadata scan,
но не удержания всех XML-деревьев в памяти. Large-config приёмка и RAM требуют
отдельного фактического измерения; эта документация не объявляет p95 результат.

## Проверка и границы доказательств

`tests/integration/test_project_core_metadata.py` публикует реальный S1 через Go
scanner и Windows capture, останавливает enrichment перед nested form read,
изменяет XML, удаляет живые module/rights files и публикует S2. Все возвращённые
XML/form/module/rights refs и bytes остаются S1. Дополнительно меняется объявленный
формат текущей source configuration: старый reader сохраняет descriptors S1.
Три слоя с одинаковыми именами/UUID/путями остаются отдельными. Другой principal
и отозванный membership не достигают retained IO.

Unit-тесты проверяют DTD в UTF-8/UTF-16 LE/BE, invalid encoding/XML, byte/node/depth
bounds, отсутствие скрытых нулей, смешанное format coverage, полный session inventory,
точные object selectors, ограничение коллекций и отзыв доступа во время чтения.
Это не свидетельство live 1C execution, canonical metadata UUID, structural apply,
полного EDT, форм-дизайнера, HTTP cutover или завершения E1–E4.

Первичные API references: [ElementTree custom TreeBuilder](https://docs.python.org/3.11/library/xml.etree.elementtree.html#xml.etree.ElementTree.TreeBuilder),
[Python XML vulnerabilities](https://docs.python.org/3.11/library/xml.html#xml-vulnerabilities).


## Evidence v2 и привязка полного прохода

`parser="designer_xml_v1"` не меняется: грамматика, полнота и ограничения
интерпретации сохранены. `evidence_schema="metadata_scan_v2"` меняет observable
смысл `source_refs`: клиент больше не вправе считать длину этого списка числом
просмотренных XML. В нём остаются точные refs выбранного результата, configuration
и bounded witnesses. Остальные просмотренные документы представлены counts и
хешем набора входов. Лимит HTTP 2 MiB сохраняется; большие scalar values или
много слоёв могут по-прежнему привести к явному отказу по лимиту.

`validation_summary.generation` содержит flat `project_id`, `snapshot_id`,
`manifest_hash`, `source_digest`, `graph_hash`, `verified_source_files`,
`verified_derived_files`, `verified_source_bytes`, `verified_total_bytes`,
`all_expected_files_verified=true`, `inventory_checks="entry_exit"`,
`expected_bytes_protected="retained_handles"`,
`temporal_namespace_atomicity="not_proven"`. Эта часть появляется только после
успешного завершения сессии, финальной авторизации и закрытия handles. Полная
проверка включает opaque источники, derived files и graph, даже если metadata
их не интерпретирует. Manifest hash идентифицирует весь ожидаемый набор.

`validation_summary.metadata_scan` содержит `selected_layers` в порядке ordinal,
`selection_policy="designer_candidates_unless_edt_or_mdo_v1"`,
`all_selected_candidates_examined`, а также два независимых счётчика:

- `xml_candidates`: `candidate_count`, `parsed_count`, `matching_root_count`,
  `refs_sha256`. Root/type mismatch не превращается в supported слой; полные
  counts относятся к фактическому проходу, даже если его итог unsupported.
- `opaque_mdo`: `verified_count`, `refs_sha256`; это raw verification, не XML parse.

Per-layer `format_decision.scan` содержит те же counts/digests для одного слоя
и status. Declared EDT или любой `.mdo` дают XML status
`skipped_unsupported_format`, `parsed_count=0`, `matching_root_count=0`.
XML может пройти generation hash verification, но это не означает XML-разбор.
Если выбран хотя бы один такой слой, `all_selected_candidates_examined=false`.
EDT без `.mdo` остаётся unsupported с нулевым opaque count и без выдуманного ref.
При отсутствии XML candidates в обычном слое status `no_candidates`, поддержка
тоже не объявляется. `.mdo` count имеет status `verified_bytes` или `absent`.

Digest определяется точно: SHA256 от canonical JSON (`canonical_bytes`) объекта
с `domain="rentgen.metadata.examined_refs.v1"`, полным `snapshot`,
`parser="designer_xml_v1"`, `selected_layers`, `kind` (`xml_candidates` либо
`opaque_mdo`) и `records`. Каждый record имеет `layer_id`, `relative_path`,
`raw_sha256`; порядок — ordinal слоя, затем UTF-8 bytes полного пути. В records
входят только фактически разобранные XML либо проверенные opaque `.mdo`, отдельно.
Per-layer digest использует selected_layers из единственного layer_id.

Digest связывает наблюдение reader с воспроизводимым набором входов; это не
подпись и не самостоятельное криптографическое доказательство разбора или counts.
Для независимой проверки можно перечислить source pages того же снимка,
применить опубликованное правило candidates, прочитать exact refs и воспроизвести
разбор/хеш. Нового persisted index, proof receipt или скрытого cache нет.

Summary и search разбирают XML по одному, сохраняют только counts и bounded
previews. Search limit 1 не останавливает поиск до последнего кандидата: поздний
matching объект влияет на exact total, поздний root mismatch отменяет provisional
результаты всего слоя. Object сохраняет дерево только exact выбранного объекта;
его формы, права и модули читаются до выхода из той же сессии. Проверки deadline
выполняются до/после parse и materialization. Результат не выдаётся до exit inventory;
временно созданный и удалённый между проверками неиспользованный файл не объявляется
обнаруженным.
