# Рентген Core 0.1.0.dev19



Предварительный выпуск компонентов. Основной комплект: Windows x64 /
CPython 3.11. Отдельное дополнение GNU/Linux x86_64 остаётся экспериментальным.
Общая готовность продукта: `full_product_ready=false`.

## Изменения после dev17

- CLI `draft-start` начинает ручной черновик по точной ссылке на сохранённый
  модуль; `draft-edit` изменяет ожидаемую ревизию ограниченными точными заменами.
  Создание, сохранение версии, проверка и применение остаются разными операциями.
- Результаты поздно завершившихся BSL-, платформенных и функциональных проверок
  не должны подменять уже изменившийся контекст выбранного черновика в Companion.
  Сохранение и чтение квитанции поддерживают восстановление потерянного ответа.
- Ошибки запуска Observer возвращаются в структурированном виде. Сохранённые
  сведения анализа привязываются к проверенным входам и зависимостям анализатора.
- Экспериментальный `rentgen-gui` открывает локальную графическую область:
  Designer XML ZIP, поиск объектов и их прямых реквизитов/измерений/ресурсов,
  поиск модулей по пути и именам, буквальный поиск исходников и вхождений,
  проверенные UTF-8 байты и SHA-256. Поля показываются с объектом-владельцем
  и точным XML-происхождением; это ограниченный поиск, без семантического индекса.
- Два явно загруженных ZIP дают инвентарь изменений по пути/размеру/SHA-256,
  исходные панели, ограниченный построчный diff и полный HTML/JSON отчёт.
  Три ZIP с ролями Base/Current/Upstream дают отдельный инвентарь, включая удаления.
  Эти результаты не доказывают общее происхождение, безопасность merge или
  применимость конфигурации. Автоматического merge/apply нет.

GUI работает локально, без LLM и отправки исходников в облако. Он не меняет
исходный ZIP, живую базу, project head, snapshots или drafts и не выполняет
диагностику конфигурации. Экспериментальный диагностический Rust kernel в
репозитории не является поставленной диагностикой живой базы.

## Установка Windows-комплекта

Скачайте `rentgen-core-0.1.0.dev19-windows-py311.zip`, `manifest.json` и
`SHA256SUMS`. До распаковки проверьте размер и SHA-256 по manifest:

```powershell
Get-FileHash -LiteralPath .\rentgen-core-0.1.0.dev19-windows-py311.zip -Algorithm SHA256
```

Принятый ZIP: `20809034` байт,
SHA-256 `6b75cb14aa453451d3f3d59952ae099a39f15fc13c40d8a32dd32ce443f4d906`.

Распакуйте в новую папку. В каталоге `rentgen-core-0.1.0.dev19-windows-py311`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --only-binary=:all: --require-hashes --find-links . --find-links .\wheels -r .\mcp-requirements.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\rentgen.exe --help
.\.venv\Scripts\rentgen-mcp.exe --help
```

Python, редактор, модель, Java/BSL-LS и платформа 1С устанавливаются отдельно.
[Регистрация проекта и первый снимок, шаги 2–3](https://github.com/DmitrL-dev/1cai-public/blob/5eee97ea050c9f4c06eaceb4d191f16868fb0141/GETTING_STARTED.md#2-зарегистрируйте-проект).
Вступление и шаг установки этого source-bound руководства ещё описывают прежнюю
опубликованную пару; для dev19 используйте точные команды выше.

Companion новой пары — **0.1.20**. Создайте новый отдельный профиль по
[инструкции адаптера точных исходников](https://github.com/DmitrL-dev/1cai-public/blob/5eee97ea050c9f4c06eaceb4d191f16868fb0141/integrations/open-editor/README.md),
указав Python именно установленного dev19, свои registry/project ID и scanner.
При прерывании сначала прочитайте квитанцию прежней операции; не повторяйте
запись вслепую. Recovery не разрешает перезаписывать посторонние изменения.

## Экспериментальное дополнение Linux

- `rentgen-core-0.1.0.dev19-experimental-linux-x86_64.tar.gz`;
- `experimental-linux-manifest.json`;
- `experimental-linux-SHA256SUMS`.

Дополнение содержит канонический wheel из принятого Windows-комплекта,
Linux Rust input core из CI, лицензии, provenance и scoped `INSTALL.md`.
Архив: `982299` байт, SHA-256 `e15b226c3979798ce6cf32dcdcf5bbfe18404e12d8c2aa850560b4d1be7533d2`.
Это не полный offline MCP-комплект; Go scanner и редактор в него не входят.
Нужны GNU/Linux x86_64, glibc 2.34+, `libgcc_s.so.1`, kernel 5.9+, memfd seals
и `/proc/self/fd`. Следуйте `INSTALL.md` из архива для отдельного окружения,
явной local identity и запуска `rentgen-gui`; хэш helper берите из manifest.
Ссылка запуска содержит временный ключ сеанса: не публикуйте её.

ZIP: до 16 МиБ, 4096 записей, 4 МиБ на файл, 32 МиБ распакованных данных.
Просмотр исходника: строгий UTF-8 до 256 КиБ, результаты — страницы по 200.
Построчный diff: до 4096 строк на сторону, 8192 строк результата и
1 000 000 ячеек выравнивания; при превышении бюджета остаются исходные панели.
ZIP не извлекается в файловую систему. Поиск и сравнение ограничены
принятыми байтами, не подтверждают полноту выгрузки или соответствие живой базе.

Границы и команды: [локальный GUI](https://github.com/DmitrL-dev/1cai-public/blob/5eee97ea050c9f4c06eaceb4d191f16868fb0141/docs/product/LOCAL-GUI.md),
[Rust input core](https://github.com/DmitrL-dev/1cai-public/blob/5eee97ea050c9f4c06eaceb4d191f16868fb0141/docs/product/RUST-INPUT-CORE.md),
[local ownership и capabilities](https://github.com/DmitrL-dev/1cai-public/blob/5eee97ea050c9f4c06eaceb4d191f16868fb0141/docs/product/PORTABLE-CORE.md).

## Привязка и фактическая приёмка

Исходники принятого Windows ZIP и цель Core tag: `5eee97ea050c9f4c06eaceb4d191f16868fb0141`;
дерево: `0e1bcfc82561e01091ad4c2a9274738739a982e8`. Release records фиксируются позднее и не подменяют
байты этой сборки. SHA-256 канонического wheel: `c37920f5bdddadcd42dacfebbbf11dd877a40d0ae890a8d26b5c01732ac590b0`.
Точные runs/artifacts, внешние digest и размеры сохраняет
[qualification.json](https://github.com/DmitrL-dev/1cai-public/blob/companion-v0.1.20/releases/core/0.1.0.dev19/qualification.json)
в неизменяемом дереве записи выпуска.

- [Windows Product checks](https://github.com/DmitrL-dev/1cai-public/actions/runs/38701365219): 4116 Python passed,
  532 skipped, 0 failures/errors. В JUnit 4648 testcase; header 4699 дополнительно
  учитывает 51 успешный subtest. Preflight 95 входит в полный suite и повторно
  не прибавляется. Node: 430 passed, 0 skipped; Go прошёл.
- Двойная сборка дала одинаковые bytes; офлайн-установка проверила 40 файлов,
  30 dependency wheels, hash lock и 33 инструмента официального MCP SDK.
  Установленные snapshot comparison и Observer в отдельных процессах прошли.
- [Companion → установленный dev19 CLI](https://github.com/DmitrL-dev/1cai-public/actions/runs/38701365219): один настоящий
  межклиентский сценарий создал ревизии 1/2/3, сохранил ручной черновик,
  восстановил точную квитанцию потерянного ответа, внёс отдельную CLI-ревизию
  и отказал устаревшему повторному изменению. Исходник и прежняя история сохранены.
  Это service integration, без GUI настоящего редактора.
- Настоящий SCM lifecycle, scoped Git ownership diagnostic и stock Git/BSL
  lifecycle прошли; службы удалены и cleanup errors отсутствуют. Stock interruption
  покрывает quiet continuous wait, не активный BSL; raw BSL report не сохранялся.
  Git diagnostic не принимает сам по себе continuous Git или production trust policy.
- [Linux portable Python 3.11/3.12](https://github.com/DmitrL-dev/1cai-public/actions/runs/38701365128): в каждой lane
  318 passed / 1 skipped целевых portable контрактов и 315 GUI контрактов без
  отказов/пропусков. Полный suite имеет 4648 testcase: 3605 passed, 90 failures,
  2 errors, 951 skipped; дополнительно 53 успешных subtests учтены header 4701.
  Новых failure IDs и отсутствующих baseline cases нет. Baseline gate принят;
  полный Linux suite не зелёный.
- [Браузер установленного пакета](https://github.com/DmitrL-dev/1cai-public/actions/runs/38701365237): 963 backend и 43 browser
  случая без отказов/пропусков. Обычная sandbox Chromium, клавиатура, narrow
  viewport и настоящий 200% zoom. Три точных CI screenshot просмотрены Codex;
  блокирующих визуальных замечаний нет. Это не человеческая usability-приёмка.
- [Финальный извлечённый Linux supplement](https://github.com/DmitrL-dev/1cai-public/actions/runs/38705066182):
  канонический Windows wheel и выбранный Linux CI helper сохранены побайтно;
  в той же Linux-среде повторная каноническая реконструкция совпала по SHA-256
  сжатого архива. Между разными zlib/ОС одинаковые gzip bytes не обещаются.
  Свежая установка из извлечённого supplement,
  installed `rentgen-gui`, все 9 static assets, HTTP→Rust импорт и hash-bound source,
  отказ без session/с чужим Origin, остановка и очистка прошли. Все 43 sandboxed
  browser сценария прошли без пропусков на этой установке; project/input bytes
  сохранились. Квитанции: `experimental-linux-installation.json` и
  `experimental-linux-qualification.json` рядом с qualification в записи выпуска.
- Дополнительно упаковка из квалифицированных входов в двух новых каталогах
  на macOS (Python 3.11.15, zlib 1.2.12) дала одинаковые три файла, побайтно
  совпавшие с исходными CI bytes. Это проверка сборки пакета, не запуск Linux
  на macOS и не универсальная гарантия для других zlib. Квитанция:
  `experimental-linux-packaging.json`. Для публикации сохраняются исходные CI файлы.

Companion tag workflow и публичная проверка файлов выполняются следующими
этапами; успешный результат в этих notes заранее не заявляется. После публикации
в main добавляется отдельная квитанция публичных downloads и tag workflow.

## Ограничения выпуска

Linux capture/retained snapshots, запись черновиков, Observer, live apply,
native 1С и Companion этим дополнением не приняты. Windows/macOS GUI
не квалифицированы. Source-facts PR #84 остаётся отдельным незавершённым draft
и в состав принятого дерева не добавляется.

Этот выпуск не заявляет новую установку/приёмку в настоящем редакторе,
native 1С business acceptance, качество AI, cold OwnerIPC, обновление типовых
конфигураций или готовность полной IDE. Исторические native-опыты относятся
к своим версиям. Ускорение без сопоставимых измерений не заявлено.
Прежние теги, release records и публичные assets сохраняются без перезаписи.
