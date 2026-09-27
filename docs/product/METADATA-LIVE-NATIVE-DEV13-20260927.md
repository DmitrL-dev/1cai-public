# Core dev13: переименование реквизита, данные и Undo на 1С

27 сентября 2026 года установленный **принятый CI-комплект dev13** проверен
на собственном синтетическом Designer XML примере
`Catalog.Products.Attribute.Article → SKU` и новых файловых базах
**1С 8.3.27.2342 / YAxUnit 25.12**. На момент опыта dev13 ещё был черновиком
релиза, а CI объединённого main выполнялся.

## Поставка и происхождение проверки

- Исходный коммит комплекта: `1519d8bbf0c5aabb4e804e88640a98bacff44a93`.
- ZIP: `1fb3ee3a41dd30a1efc754f41297a0ae930a1a31f994df5f9a695c7b12ac0de6`.
- Wheel: `b7b26fcd446e1841bcbc7ef1cb3f4797dd4fc992dfbe212c4555d07bb948b6cd`.
- Scanner: `8d81c1eda05d9c358385396861eb1df611d83489582f7293ad461c45017817c4`.
- Все **103 файла** Core, Graph и Diagnostics сверены с wheel до и после опыта.
  Внутренняя проверка штатного verifier отдельно проверяет 93 файла Core/Graph.
- Штатный [verifier](../../scripts/verification/verify_metadata_live_native.py)
  взят из main `acfb69dadea81e7a8caec8ed7834c97f510fbb33`. Во временной копии изменены только
  ожидаемые версия/хэш dev13 и описание статуса, путь к проверенным fixtures
  и удалена вставка source checkout в Python import path. Продуктовый пакет
  не редактировался. Дельты и хэши трёх файлов записаны в квитанции.

## Запись исходника и нативная загрузка

1. Созданы собственный source, registry, snapshot и сохранённый preview
   из проверенного fixture. EDT в этом опыте не запускался.
2. Read-only preflight сохранил прежний статус `unavailable`; отдельный
   поддержанный live writer применил операцию к исходнику.
3. Изменились только `Catalogs/Products.xml` и привязка поля в
   `Catalogs/Products/Forms/ItemForm/Ext/Form.xml`. Полный inventory совпал
   с retained candidate.
4. Этот source закреплён на время загрузки в новую файловую базу.
   Create, LoadConfigFromFiles, UpdateDBCfg, CheckConfig в четырёх контекстах
   и DumpConfigToFiles прошли. UUID каталога, реквизита и формы, длина 32,
   field ID и привязка `Объект.SKU` сохранились.
5. CAS undo вернул `undone`. Все **пять исходных файлов** восстановлены
   по размеру и SHA256. Дайджест original/restored:
   `e4099571515b28588939bd20df1b29deb39d76dbb16b21b4a8012eaf12de254b`.

## Данные и отрицательный контроль

Отдельная новая база использовала те же original, normalized и candidate
inventory. Проверены **три записи**: Unicode, пустая строка и 32 символа,
а также полные ссылки записей без усечения UUID.

| Фаза | Результат |
| --- | --- |
| Создание данных (`seed`) | 1 passed |
| Повторное открытие исходной схемы | 1 passed |
| Нормализованная схема | 1 passed |
| Переименование Article → SKU | 1 passed |
| Возврат исходной схемы | 1 passed |
| Подмена UUID реквизита | 1 ожидаемый failure, 0 errors |

При подмене UUID конфигурация компилируется, но проверка данных обнаружила
пустую строку вместо `01234567890123456789012345678901` в
`RentgenMigrationData.ПроверитьДанные`. Поэтому отрицательный опыт проверяет
потерю значений, а не только наличие любой ошибки.

Все **36 записанных шагов** платформы/ibcmd завершились с кодом 0.
Хэши существующих log/stdout/stderr сверены с файлами; у ibcmd
`extension-properties` проверены его stdout/stderr. Все шесть JUnit,
exit-файлы и settings также сверены.

## Доказательства и границы

- [Квитанция root-проверки](evidence/metadata-live-native-dev13-20260927.json),
  SHA256 `8f98a53789297737e6505d6a2a099332f55bc8fbef54f56ca259e1df994cf684`.
- [Исходный результат verifier](evidence/metadata-live-native-dev13-20260927.raw.json),
  SHA256 `89e52e3131ad09535aeb651393ec807c99f7dd45462c27e5e88aab8811067490`.
- Operation ID: `027c0892-4d3b-43a2-8b04-33d9986b71c2`.

Это проверка установленного принятого CI wheel на собственной синтетической
выгрузке. Произвольные конфигурации, `.cf/.cfe`, самостоятельные изменения форм
и СКД, внешние конкурентные записи, реальный EDT producer и production
deployment этим опытом не квалифицируются. Работа выполнена без субагентов;
новое независимое peer review не заявляется.
