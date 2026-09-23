# Core dev10: native proof прямой записи Designer XML

23 сентября 2026 года установленный публичный Core `0.1.0.dev10` прошёл
сквозной опыт на собственном синтетическом Designer XML примере
`Catalog.Products.Attribute.Article → SKU`. Проверены 92 установленных файла
Core против wheel внутри [публичного ZIP](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev10),
а также байты `bsl-scan.exe`. SHA256 ZIP:
`11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`.

## Что выполнялось

1. Скопирован точный `edt-metadata-v1/created` в новое зарегистрированное
   дерево на фиксированном локальном томе. Полный inventory совпал с fixture
   manifest.
2. Core создал snapshot и сохранённый preview на базе fixture
   `created`/`renamed`. В этом опыте EDT не запускался: происхождение preview
   синтетическое и отражено в машинной квитанции.
3. Старый read-only preflight сохранил intent и вернул `unavailable` с
   `live_apply_not_implemented`/`normalization_not_qualified`. Отдельный
   writer dev10 проверил тот же intent, применил операцию и изменил два файла
   зарегистрированного дерева: метаданные каталога и привязку поля формы.
4. Полный inventory **живого источника после записи** совпал с retained
   candidate. Именно этот каталог был загружен через `/LoadConfigFromFiles`
   в новую файловую базу 1С 8.3.27.2342. `/UpdateDBCfg`, `/CheckConfig` в
   четырёх контекстах и `/DumpConfigToFiles` завершились с кодом 0.
   Обратная выгрузка сохранила UUID каталога, реквизита и формы, длину 32
   и привязку поля к `SKU`.
5. `undo_live` с compare-and-swap вернул `undone`; полный inventory после
   восстановления совпал с исходным.
6. Отдельная нативная проверка 1С/YAxUnit 25.12 на тех же original,
   normalized и candidate inventory проверила три записи: Unicode, пустую
   строку и значение длиной 32 символа. Фазы `seed`, `reopen-original`,
   `normalized`, `renamed`, `restored` прошли. С изменённым UUID реквизита
   тест данных ожидаемо завершился одним failure.

SHA256 полного inventory: исходный и восстановленный —
`e4099571515b28588939bd20df1b29deb39d76dbb16b21b4a8012eaf12de254b`;
после live apply —
`a1d8bb9148b3a1081d59541e43bddd8cb5651de18018c98129b4c823e6ac5c39`.
Preview ID `d71a9c373fcc55317b1133381dfe5e41e0a057247a6d2f16866f8b0571bae935`,
operation ID `3b11a2bd-89af-4324-a2e4-9bc59184ef5b`.

Краткая [машинная квитанция](evidence/metadata-live-native-dev10-20260923.json)
содержит хэши входов, коды native шагов и результаты тестов. Повторяемый
[verifier](../../scripts/verification/verify_metadata_live_native.py) принимает
пути к публичному ZIP и его `bsl-scan.exe`, установленным `1cv8.exe`/`ibcmd.exe`,
YAxUnit CFE, ожидаемые SHA256 и новый `--output` на фиксированном локальном
томе. В каталоге запуска остаются полные локальные native журналы и отчёты.

## Пределы вывода

Доказана прямая запись ограниченного Designer XML источника с последующим
нативным импортом и восстановлением источника. Core не обновлял рабочую
информационную базу. Бизнес-прогон на тех же хэшах candidate использовал
отдельную новую файловую базу. Эта квитанция не квалифицирует произвольные
конфигурации, `.cf/.cfe`, расширения, формы/СКД как самостоятельные изменения,
внешние конкурентные записи и производственное развёртывание.
