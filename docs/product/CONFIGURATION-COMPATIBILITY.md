# Матрица чтения метаданных EDT

Эта матрица фиксирует ограниченный контракт чтения, покрытый синтетическими
Python-тестами. Она не квалифицирует конфигурацию для EDT/1С, изменение данных
или применение изменений. В этом срезе EDT и 1С не запускались; runtime API и
их контракты не менялись.

## Значение статусов

| Статус в матрице | Что подтверждено |
| --- | --- |
| Чтение identity | `edt_metadata_inventory` возвращает UUID, имя, тип, XML location, прямого owner и SourceRef прочитанного MDO; всегда `coverage: partial` |
| Bounded projection | Другой API общего metadata reader извлекает ограниченные поля; это не полнота inventory и не семантическая валидность |
| Atomic comparison | Designer three-way распознаёт UUID-bound companion и сравнивает целые байты; `supported` относится к этому сравнению |
| Opaque count | EDT identity inventory учитывает только путь в `unparsed_files`, не читает содержимое и не возвращает его SourceRef |
| Неподдержано | Заданный контракт отказывает или выдаёт явную unsupported-причину; частичный candidate не разрешается |
| Не квалифицировано | Для данной комбинации нет native acceptance; наличие parser vocabulary не меняет этот статус |

Статусы разных API не взаимозаменяемы. Словарь `FOLDER_TO_TYPE` шире девяти
примеров ниже, но распознавание имени каталога не доказывает совместимость
объекта или его свойств с платформой.

## Девять представительных корневых типов

Корпус сохранён в
[`edt-inventory-v1`](../../packaging/fixtures/edt-inventory-v1/README.md): девять
MDO, 17 identities, пять opaque assets и шесть отрицательных XML-примеров.
Manifest задаёт `provenance: synthetic`, `scope: read_only_contract`, хэши/размеры,
ожидаемые UUID/owner/layer и отсутствие live/native/container acceptance.
[`test_edt_inventory_fixture.py`](../../tests/unit/test_edt_inventory_fixture.py)
сравнивает результаты с manifest и отдельно проверяет параметризованные границы.
Пары путь/тип заданы явно и не выводятся из словаря реализации. Минимальный XML
создан для проверки reader; обязательные для реальной конфигурации свойства
в него не добавлялись. Все девять строк имеют статус **чтение identity** и
**не квалифицировано для native исполнения данного синтетического входа**.

| Тип | Синтетический путь | Что проверяет строка |
| --- | --- | --- |
| Configuration | `Configuration/Configuration.mdo` | Прямое имя Demo, UUID, `owner: null`; имя Configuration из пути не навязывается |
| Catalog | `Catalogs/Products/Products.mdo` | Привязка Products к пути, тип, UUID, SourceRef |
| Document | `Documents/Order/Order.mdo` | Привязка Order к пути, тип, UUID, SourceRef |
| InformationRegister | `InformationRegisters/Prices/Prices.mdo` | Привязка Prices к пути, тип, UUID, SourceRef |
| Enum | `Enums/State/State.mdo` | Привязка State к пути, тип, UUID, SourceRef |
| CommonModule | `CommonModules/Helpers/Helpers.mdo` | Identity дескриптора; BSL не разбирается |
| CommonForm | `CommonForms/Search/Search.mdo` | Identity дескриптора; структура формы не квалифицируется |
| Report | `Reports/Sales/Sales.mdo` | Identity дескриптора; СКД не квалифицируется |
| CommonTemplate | `CommonTemplates/Layout/Layout.mdo` | Identity дескриптора; содержимое макета не квалифицируется |

`test_representative_root_identity_contract` проверяет полную строку identity,
включая SHA256 SourceRef и декларацию слоя. У корневых объектов `owner: null`:
владение со стороны Configuration не выводится из структуры каталогов.

## Семь embedded declarations

Каждая строка `test_embedded_declaration_matrix` проверяется с unqualified и
metadata-qualified XML names. Результат содержит owner с UUID непосредственного
XML-родителя, SourceRef того же MDO и точный XML path. Индекс учитывает также
элементы свойств перед декларацией.

| Декларация | Тип identity | Представительный родитель | Статус |
| --- | --- | --- | --- |
| `attributes` | Attribute | Catalog | Чтение identity |
| `tabularSections` | TabularSection | Document | Чтение identity |
| `dimensions` | Dimension | InformationRegister | Чтение identity |
| `resources` | Resource | InformationRegister | Чтение identity |
| `forms` | Form | Catalog | Чтение identity, без чтения `.form` |
| `commands` | Command | Catalog | Чтение identity, без выполнения команды |
| `enumValues` | EnumValue | Enum | Чтение identity |

Дополнительно существующий `test_nested_owner_is_the_immediate_tabular_section`
в [`test_edt_inventory_metadata.py`](../../tests/unit/test_edt_inventory_metadata.py)
проверяет attribute внутри tabular section. Другие вложенные owners и неизвестные
identity-bearing элементы отклоняются. Таблица не задаёт платформенную матрицу
допустимых сочетаний каждого типа и свойства.

## Форматы, companions и расширения

| Вход / операция | Текущий статус | Evidence и ограничение |
| --- | --- | --- |
| Корневой `.mdo`, явно объявленный EDT слой | Чтение identity | Новый synthetic corpus и существующие UUID/namespace/path/limit tests; полный EDT inventory не заявляется |
| EDT `.form` | Opaque count в identity inventory; bounded projection в общем reader | `test_non_mdo_assets_are_counted_without_reading_or_claiming_content`; отдельно [`test_metadata_edt.py`](../../tests/unit/test_metadata_edt.py) проверяет синтетическую форму и поля |
| BSL в EDT дереве | Opaque count | Содержимое не анализируется этим inventory, независимо от предполагаемого owner |
| Designer BSL companion | Atomic comparison; узкая qualified сборка раздельных text edits | [`METADATA-THREE-WAY-SEMANTICS.md`](METADATA-THREE-WAY-SEMANTICS.md); это отдельный API, без компиляции и исполнения |
| Designer форма | Atomic comparison | UUID-bound descriptor и shape; ID/события/ссылки не проверяются этим planner |
| СКД XML в EDT дереве | Opaque count | Синтетические байты по nested template path не читаются inventory |
| Designer СКД companion | Atomic comparison | Требуются owner, `TemplateType=DataCompositionSchema` и namespace; конкурирующие изменения остаются конфликтом, выполнение запроса не проверено |
| `.cf`, `.cfe` в manifest | Opaque count | Даже некорректные binary bytes не читаются и не получают SourceRef; импорт контейнера не производится |
| `source_format="cf"` / `"cfe"` | Неподдержано | `SourceLayerSpec` возвращает `SOURCE_LAYER_INVALID`; эти контейнеры не являются source format для snapshot reader |
| Явный слой `kind="extension", source_format="edt"` | Только отдельное наблюдение identities | Один UUID в base и extension даёт две строки; adoption/override/effective ownership не выводятся |
| Неизвестная identity-bearing декларация расширения в MDO | Неподдержано | `EDT_INVENTORY_UNSUPPORTED`; это synthetic malformed/unknown shape, не принятая схема EDT extension |
| Designer `ObjectBelonging`, `ExtendedConfigurationObject`, `ConfigurationExtensionPurpose` | Неподдержанная extension semantics | `extension_ownership_unverified` даже при unchanged bytes; materializer блокирует весь candidate |

Отсутствие содержимого opaque assets в SourceRef не означает, что binary/XML
валиден или безопасен для запуска. Подтверждено только то, что данный inventory
не использует эти байты. Платформенная поддержка произвольных расширений и
типовых `.cf/.cfe` остаётся не квалифицирована.

## Существующие native evidence имеют отдельную область

| Evidence | Фактическая область | Что не следует из результата |
| --- | --- | --- |
| [`edt-metadata-v1.json`](evidence/edt-metadata-v1.json) | Собственная Configuration/Catalog/Attribute/Form, EDT 2026.1.3 и платформа 8.3.27.2342, rename и выбранные структурные инварианты сохранённых Designer XML | Native acceptance новых минимальных MDO, произвольных объектов и типовых конфигураций |
| [`metadata-migration-v1.json`](evidence/metadata-migration-v1.json) и [описание](METADATA-MIGRATION.md) | Три записи одного строкового реквизита, rename/возврат и отрицательный UUID case; YAxUnit 25.12 как внешний закреплённый движок | Общая совместимость `.cfe`, сохранность всех данных и business logic |
| [`ibcmd-roundtrip-8.3.27.2342-20260914.json`](evidence/ibcmd-roundtrip-8.3.27.2342-20260914.json) | Локальный unattested create/import/export собственной фикстуры через `candidate.cf` | Импорт произвольного `.cf`, межзапусковая побайтная воспроизводимость и live apply |
| [`metadata-native-apply-20260914.json`](evidence/metadata-native-apply-20260914.json) | EDT import/rename/export и owned workspace apply/undo на собственной фикстуре | В этом smoke не запускался новый platform/business check; `live_apply_allowed=false` |

Синтетические тесты этого документа не обновляют и не расширяют перечисленные
native evidence. Данных пользовательских конфигураций в новом корпусе нет.

## Отказы и лимиты

Новые тесты закрепляют имена (пустое, whitespace, начальная цифра, 257 символов,
вложенная разметка), положительные имена в 256 символов и кириллицу; одинаковые
имена под разными owners; независимость от порядка manifest entries; суммарные
лимиты выбранных base/extension layers и поздний отказ без частичного inventory.
Существующие тесты сохраняют UUID normalization/duplicates, неправильные
namespace/path/type, DTD, revoked authorization и ошибки лимитов.

Потолки `EDTInventoryLimits`: XML 4 MiB на документ, 50 000 nodes, depth 64,
manifest 20 000 entries, чтение 64 MiB суммарно, 2 048 MDO и 20 000 identities
на всю операцию по выбранным слоям. Ограничения можно понижать; успешный ответ
не обрезается. Они не являются допустимыми размерами платформенной конфигурации.

## Повторить contract checks

Команды выполняются из корня репозитория без запуска EDT/1С:

```powershell
py -3.11 -m pytest -q tests/unit/test_edt_inventory_fixture.py tests/unit/test_edt_inventory_metadata.py tests/unit/test_metadata_edt.py tests/unit/test_edt_metadata_fixture.py tests/unit/test_metadata_three_way_semantics.py
py -3.11 -m black --check tests/unit/test_edt_inventory_fixture.py
py -3.11 -m ruff check tests/unit/test_edt_inventory_fixture.py
py -3.11 -m compileall -q tests/unit/test_edt_inventory_fixture.py
git diff --check
```
