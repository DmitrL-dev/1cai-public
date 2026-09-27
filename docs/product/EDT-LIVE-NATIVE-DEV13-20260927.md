# Core dev13: свежий EDT preview → исходники → 1С/YAxUnit → Undo

27 сентября 2026 года установленный публичный **Core 0.1.0.dev13** прошёл
цепочку переименования `Catalog.Products.Attribute.Article → SKU` через
**живой EDT 2026.1.3 / MCP 2.16.1**, собственный Designer XML source и новые
файловые базы **1С 8.3.27.2342 / YAxUnit 25.12**.

Это отдельный опыт после проверки синтетического сохранённого preview:
здесь EDT заново импортировал исходники, сформировал preview, выполнил
переименование и экспортировал candidate. Зарегистрированный исходник
во время preview остался прежним.

## Происхождение и неизменность входов

- Публичный [Core dev13](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev13),
  исходный коммит `1519d8bbf0c5aabb4e804e88640a98bacff44a93`.
- ZIP: `1fb3ee3a41dd30a1efc754f41297a0ae930a1a31f994df5f9a695c7b12ac0de6`.
- Wheel: `b7b26fcd446e1841bcbc7ef1cb3f4797dd4fc992dfbe212c4555d07bb948b6cd`.
- Scanner: `8d81c1eda05d9c358385396861eb1df611d83489582f7293ad461c45017817c4`.
- Все **103 файла Core/Graph/Diagnostics** совпали с принятым wheel до и после
  опыта. Внутренняя проверка verifier отдельно сверила 93 файла Core/Graph.
- Все **1441 файл EDT/Java** совпали с зарегистрированными размерами и SHA256
  до и после опыта: 1262 файла EDT и 179 файлов Java. Профиль не изменился.
- Использован штатный verifier `verify_edt_live_native_dev10.py` из main
  `acfb69dadea81e7a8caec8ed7834c97f510fbb33` и три его помощника.
  Во временной копии изменены только ожидаемые версия/ZIP hash и подписи dev13,
  ROOT проверенных fixtures; удалена вставка source checkout в import path.
  Продуктовые пакеты и BSL fixtures не редактировались. Дельты сохранены в квитанции.

## Свежий EDT preview и запись

EDT сохранил **10 MCP-запросов**. Три ранних `get_metadata_details` были
вернули `Could not get configuration for project: RentgenCandidate`;
следующий запрос прошёл. Импорт,
экспорт, rename preview с `confirm:false` и исполнение с `confirm:true`
получили ответы. Проверены совпадение `expectedHash` с preview,
`performedCount: 1`, `errors: 0` и штатное закрытие runtime.

- Preview operation: `e725ee67-da0a-49e4-b937-b2b9010a0b7a`.
- Preview digest: `3443469ca394acdf096219e824920765fce650677682cc0fbe4349f9064db1bd`.
- Apply/Undo operation: `743ca00f-1aeb-4b51-b757-6e398e577238`.

Read-only preflight сохранил статус `unavailable`. Отдельный поддержанный
live writer получил intent и изменил ровно два файла:
`Catalogs/Products.xml` и `Catalogs/Products/Forms/ItemForm/Ext/Form.xml`.
Полный inventory записанного источника совпал с новым EDT candidate.

Именно этот источник был закреплён на время native импорта. Создание базы,
загрузка, обновление, проверка конфигурации и обратная выгрузка прошли.
UUID каталога, реквизита и формы сохранились; длина строки — 32,
field ID — 7, привязка поля — `Объект.SKU`.

## Бизнес-данные и возврат

Отдельные проверки на тех же original/normalized/candidate inventory
сохранили три записи: Unicode, пустую строку и строку из 32 символов,
а также полные ссылки записей.

| Фаза | Результат |
| --- | --- |
| Создание данных | 1 passed |
| Повторное открытие исходной схемы | 1 passed |
| Нормализованная схема | 1 passed |
| Переименование Article → SKU | 1 passed |
| Возврат схемы | 1 passed |
| Подмена UUID реквизита | 1 ожидаемый failure, 0 errors |

Подмена UUID успешно компилировалась, но проверка обнаружила пустое значение
вместо ожидаемой строки `01234567890123456789012345678901`.
CAS Undo вернул `undone` и восстановил все **пять исходных файлов** побайтно.
Все **36 записанных шагов** платформы/ibcmd завершились с кодом 0;
ожидаемый отказ данных зафиксирован отдельно в JUnit.

- Original/restored inventory SHA256: `e4099571515b28588939bd20df1b29deb39d76dbb16b21b4a8012eaf12de254b`.
- Applied inventory SHA256: `8dc3cbb4b4fe91c32543d29125f600565a2ac1052da4173e6b294da7d083cd5c`.
- [Квитанция root-проверки](evidence/edt-live-native-dev13-20260927.json),
  SHA256 `3997e421207bcae35e24c89363e0e1b195286e4586666c0e96d73761f44170d1`.
- [Исходный результат verifier](evidence/edt-live-native-dev13-20260927.raw.json),
  SHA256 `97433cd2cd4dff17e6b38ec1e4a534850fd6d202350f839edc8a41a0fce795b8`.

## Границы

Проверены одна поддержанная операция и собственный синтетический каталог.
Типовые конфигурации, произвольные `.cf/.cfe`, расширения, формы/СКД как
самостоятельные изменения, внешняя конкурентная запись и рабочие базы
этим опытом не приняты. Production deployment не выполнялся.
Работа выполнена без субагентов; новое независимое peer review не заявляется.
