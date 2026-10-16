# Рентген Core 0.1.0.dev20



Предварительный выпуск компонентов. Основной комплект: Windows x64 /
CPython 3.11. Отдельное дополнение GNU/Linux x86_64 остаётся экспериментальным.
Общая готовность продукта: `full_product_ready=false`.

## Изменения после dev19

- Рабочее место в Companion восстанавливает выбранный снимок, источник и
  черновик после перезапуска редактора, навигация по метаданным идёт через
  выданные ядром handles, а Problems привязаны к точной сохранённой ревизии.
- Linux x86_64 в исходниках: ограниченный private capture, проверенные
  поколения графа, CAS публикации и свежее чтение source/history через CLI и MCP.
  Для capture нужен отдельно поставленный Go scanner; в Linux-дополнение он не входит.
- `snapshot-diff` и read-only MCP `rentgen_snapshot_diff` сравнивают две явные
  сохранённые версии с общим ограниченным бюджетом чтения; Windows CLI прежний.
- `test-run-qualify` (Windows) повторно сверяет сохранённые артефакты запуска
  YAxUnit — JUnit, exit, settings, журналы шагов, inventory входов, roundtrip —
  с отчётом и возвращает досье `local_unattested`. 1С при этом не запускается,
  применение недоступно.
- `rentgen capabilities` дополнительно сообщает поддержку компонентов
  (`components`); доставка уведомлений требует проверки прав перед каждой
  отправкой и подтверждением; импорт SARIF привязан к заявленному анализатору
  и его версии.

Отдельный кандидат Linux offline CLI/MCP kit (`owned-linux-cli-mcp-py311-x86_64-v1`)
не входит в этот выпуск: его собственная приёмка остаётся development-квитанцией.

## Установка Windows-комплекта

Скачайте `rentgen-core-0.1.0.dev20-windows-py311.zip`, `manifest.json` и
`SHA256SUMS`. До распаковки проверьте размер и SHA-256 по manifest:

```powershell
Get-FileHash -LiteralPath .\rentgen-core-0.1.0.dev20-windows-py311.zip -Algorithm SHA256
```

Принятый ZIP: `21020043` байт,
SHA-256 `56efbadefe6e22ff23133477e9547243d369a1e8e0f219330a47a17ee454b40c`.

Распакуйте в новую папку. В каталоге `rentgen-core-0.1.0.dev20-windows-py311`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --only-binary=:all: --require-hashes --find-links . --find-links .\wheels -r .\mcp-requirements.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\rentgen.exe --help
.\.venv\Scripts\rentgen-mcp.exe --help
```

Python, редактор, модель, Java/BSL-LS и платформа 1С устанавливаются отдельно.
[Регистрация проекта и первый снимок, шаги 2–3](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/GETTING_STARTED.md#2-зарегистрируйте-проект).
Вступление и шаг установки этого source-bound руководства ещё описывают прежнюю
опубликованную пару; для dev20 используйте точные команды выше.

Companion новой пары — **0.1.21**. Создайте новый отдельный профиль по
[инструкции адаптера точных исходников](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/integrations/open-editor/README.md),
указав Python именно установленного dev20, свои registry/project ID и scanner.
Текст этой инструкции ещё называет прежнюю пару; генератор профиля в том же
commit явно допускает dev20. При прерывании сначала прочитайте квитанцию
прежней операции; не повторяйте запись вслепую. Recovery не разрешает
перезаписывать посторонние изменения.

## Экспериментальное дополнение Linux

- `rentgen-core-0.1.0.dev20-experimental-linux-x86_64.tar.gz`;
- `experimental-linux-manifest.json`;
- `experimental-linux-SHA256SUMS`.

Дополнение содержит канонический wheel из принятого Windows-комплекта,
Linux Rust input core из CI, лицензии, provenance и scoped `INSTALL.md`.
Архив: `1089954` байт, SHA-256 `fe09f3e3b6f26310141f19489c259188914eb73524e3d820edc6e8b4d4068223`.
Это не полный offline MCP-комплект; Go scanner и редактор в него не входят.
Нужны GNU/Linux x86_64, glibc 2.34+, `libgcc_s.so.1`, kernel 5.9+, memfd seals
и `/proc/self/fd`. Следуйте `INSTALL.md` из архива для отдельного окружения,
явной local identity и запуска `rentgen-gui`; хэш helper берите из manifest.
Ссылка запуска содержит временный ключ сеанса: не публикуйте её.

Блок `platform` в `experimental-linux-manifest.json` сохраняет консервативные
исторические константы упаковщика (90 failures, 2 errors, полный suite не зелёный).
Измеренный полный Linux suite точного source commit зелёный в обеих lanes
(см. ниже); принятые bytes дополнения ради этого не пересобираются.

Границы и команды: [локальный GUI](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/LOCAL-GUI.md),
[Rust input core](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/RUST-INPUT-CORE.md),
[local ownership и capabilities](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/PORTABLE-CORE.md),
[сравнение снимков](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/SNAPSHOT-DIFF.md),
[проверка сохранённого запуска тестов](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/TEST-RUN-QUALIFICATION.md).

## Привязка и фактическая приёмка

Исходники принятого Windows ZIP и цель Core tag: `2a30f48799354fcef4bd57d1a03212fefa7f75fb`;
дерево: `bf6fcf5cd1fd5b90ab1c2ae72f6be1608a246c08`. Release records фиксируются позднее и не подменяют
байты этой сборки. SHA-256 канонического wheel: `13a526b31adc1837c1e6a5b6e758f1ca486c4c59247c9c8be60034bf097cb965`.
Точные runs/artifacts, внешние digest и размеры сохраняет
[qualification.json](https://github.com/DmitrL-dev/1cai-public/blob/companion-v0.1.21/releases/core/0.1.0.dev20/qualification.json)
в неизменяемом дереве записи выпуска.

- [Windows Product checks](https://github.com/DmitrL-dev/1cai-public/actions/runs/38846064838): 4747 Python passed,
  1160 skipped, 0 failures/errors. В JUnit 5907 testcase; header 5958 дополнительно
  учитывает 51 успешный subtest. Preflight 95 входит в полный suite и повторно
  не прибавляется. Node: 592 passed, 0 skipped; Go прошёл.
- Двойная сборка дала одинаковые bytes; офлайн-установка проверила 40 файлов,
  30 dependency wheels, hash lock и 34 инструмента официального MCP SDK.
  Установленные snapshot comparison и Observer в отдельных процессах прошли.
- Companion → установленный dev20 CLI: один настоящий межклиентский сценарий
  создал ревизии 1/2/3, восстановил точную квитанцию потерянного ответа,
  внёс отдельную CLI-ревизию и отказал устаревшему повторному изменению.
  Это service integration, без GUI настоящего редактора.
- Установленный VSIX в настоящем Windows Extension Host (VSCodium, editor API
  1.135.0): фазы first/restart, поиск метаданных через handles, отказ поддельного
  handle, сохранение ручного черновика, настоящий BSL Language Server, Problems
  точной ревизии, параллельный CLI, отказ stale и отозванной записи, восстановление
  контекста и снимка после перезапуска, согласование неподтверждённого commit.
  Модель не вызывалась, применения к 1С нет; это автоматизированное исполнение
  editor API, не человеческая приёмка клавиатуры и доступности.
- Настоящий SCM lifecycle, scoped Git ownership diagnostic и stock Git/BSL
  lifecycle прошли; службы удалены и cleanup errors отсутствуют. Stock interruption
  покрывает quiet continuous wait, не активный BSL; raw BSL report не сохранялся.
  Git diagnostic не принимает сам по себе continuous Git или production trust policy.
- [Linux portable Python 3.11/3.12](https://github.com/DmitrL-dev/1cai-public/actions/runs/38846064917): в каждой lane
  320 passed / 1 skipped целевых portable контрактов, 315 GUI контрактов и
  98 JavaScript GUI тестов без отказов/пропусков. Полный suite: 5908 testcase,
  0 failures/errors; 4922/986 (3.11) и 4921/987 (3.12) passed/skipped,
  дополнительно 53 успешных subtest учтены header 5961. Новых failure IDs и
  отсутствующих baseline cases нет; полный Linux suite зелёный. Установленный
  Linux CLI capture/restart/history/replay на synthetic fixture прошёл в обеих lanes.
- [Браузер установленного пакета](https://github.com/DmitrL-dev/1cai-public/actions/runs/38846064927): 963 backend и 43 browser
  случая без отказов/пропусков. Обычная sandbox Chromium, клавиатура, narrow
  viewport и настоящий 200% zoom. Три точных CI screenshot просмотрены Claude;
  блокирующих визуальных замечаний нет. Это не человеческая usability-приёмка.
- [Финальный извлечённый Linux supplement](https://github.com/DmitrL-dev/1cai-public/actions/runs/38848501426):
  канонический Windows wheel и выбранный Linux CI helper сохранены побайтно.
  Между разными zlib/ОС одинаковые gzip bytes не обещаются.
  Свежая установка из извлечённого supplement, installed `rentgen-gui`,
  все 9 static assets, HTTP→Rust импорт и hash-bound source, отказ без
  session/с чужим Origin, остановка и очистка прошли. Все 43 sandboxed browser
  сценария прошли без пропусков на этой установке; project/input bytes
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

Native 1С/EDT business acceptance (лицензированного стенда нет), реальное
задание модели, человеческая приёмка редактора и доступности, cold OwnerIPC,
обновление типовых конфигураций, live apply, macOS и полный Linux-продукт
остаются открытыми. Linux-дополнение не включает Go scanner, Observer,
запись черновиков, native 1С и Companion. Windows/macOS GUI не квалифицированы.
Source-facts PR #84 остаётся отдельным незавершённым draft и в состав принятого
дерева не добавляется. Классификация недостающего — в
[backlog](https://github.com/DmitrL-dev/1cai-public/blob/2a30f48799354fcef4bd57d1a03212fefa7f75fb/docs/product/BACKLOG.md).
Ускорение без сопоставимых измерений не заявлено.
Прежние теги, release records и публичные assets сохраняются без перезаписи.
