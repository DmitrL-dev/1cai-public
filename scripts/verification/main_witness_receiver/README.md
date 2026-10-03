# Main witness receiver: эксперимент для Windows x64

Это отдельная диагностическая DLL и две маленькие Node fixtures. Эксперимент проверяет, что клиент named pipe совпадает с исходным процессом, который native worker создал и продолжает удерживать. После проверки выполняются HELLO/ACK и завершение ресурсов. PID служит для сравнения и журналирования; процесс по нему повторно не открывается.

На 3 октября 2026 года Root подтвердил два свежих частных synthetic controls v4. Перенос этих исходников в репозиторий сохраняет экспериментальный статус. D8 — OPEN; EditorRole, OwnerIPC, daily/model/task, новый tag/release, полная продуктовая готовность и production deployment этим опытом не подтверждены.

Для обычной работы с Рентгеном начните с [первого запуска](../../../GETTING_STARTED.md). Этот каталог предназначен для разработчиков, изучающих Windows-проверки.

## Файлы

```text
scripts/verification/main_witness_receiver/
  README.md
  REPRODUCING.md
  source_provenance.json
  reproduce.py
  compile_data_abis.py
  admit_two_cases.py
  launch_two_cases.py
  verify_case.py
  root_main_receiver.c
  root_main_receiver.h
  root_live_debug_birth.h
  fixtures/
    parent.cjs
    child.cjs
```

| Файл | Для чего нужен |
|---|---|
| `root_main_receiver.c` | Исходный debug worker RLD и дополнительный receiver RWR в одной DLL |
| `root_main_receiver.h` | Параметры и экспортированные поля receiver; диагностические данные без передачи HANDLE/полномочий |
| `root_live_debug_birth.h` | Точный исходный RLD ABI для этой live DLL |
| `fixtures/parent.cjs` | Сначала создаёт child, затем один раз подключается и отправляет канонический HELLO |
| `fixtures/child.cjs` | Ограниченный экспериментом живой child; его окончание наблюдает native worker |
| `source_provenance.json` | Размеры/SHA исходных принятых файлов, две точные замены include и размеры/SHA публичных файлов |
| `reproduce.py` | Измеряет входы, проверяет реальные записи Source-ревью и по явному допуску оператора вызывает сборку и два controls |
| `compile_data_abis.py` | Собирает новую DLL и читает два data ABI без запуска fixtures |
| `admit_two_cases.py`, `launch_two_cases.py`, `verify_case.py` | Проверяют допуск, запускают два свежих hosts и сохраняют результаты lifecycle/IO/cleanup checks |

Соседний `../root_debug_birth.c` образует другой, самостоятельный EXE. Его header не является ABI этой DLL. Оригинальный live header размещён здесь под отдельным именем; существующий collector продолжает иметь свои контракт и доказательства.

## Сборка DLL

Понадобятся Windows x64 и GCC для Windows x64. В исходном опыте применён `C:\mingw64\bin\gcc.exe`, SHA256 `690d171db384af0f69002374a7fc4755128ee82c688d22818bd981f869a65890`. Команды ниже предназначены для PowerShell из корня репозитория:

```powershell
$gcc = 'C:\mingw64\bin\gcc.exe'
$env:PATH = (Split-Path -Parent $gcc) + ';' + $env:PATH
$receiverSource = Join-Path (Get-Location).Path 'scripts\verification\main_witness_receiver\root_main_receiver.c'
$receiverOut = Join-Path ([IO.Path]::GetTempPath()) ('rentgen-main-receiver-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $receiverOut -ErrorAction Stop | Out-Null
$receiverDll = Join-Path $receiverOut 'root_main_receiver.dll'
& $gcc -std=c11 -Wall -Wextra -Werror -O2 -shared $receiverSource -o $receiverDll -lbcrypt -ladvapi32
if ($LASTEXITCODE -ne 0) { throw "GCC failed; output retained in $receiverOut" }
Get-FileHash -LiteralPath $receiverDll -Algorithm SHA256
```

Команда только собирает DLL; native-контекст не создаётся. Размер и хеш новой DLL измеряются заново. Старый DLL pin относится к фактическому частному файлу Root; новая сборка не получает его квалификацию автоматически.

В исходном опыте были отдельно прочитаны два data ABI: исходный RLD — 12 слов, receiver — 13. RLD: `[1,8,65536,8,8368,24,16,32,152,120,20624,40]`. RWR: `[1,8,32768,8,1472,24,184,152,16,1024,4096,2,16]`. Чтение ABI не запускает две fixtures и не доказывает HELLO/ACK.

## Как читать два controls

| Контроль | Условие и исторический результат Root |
|---|---|
| `expected_parent_slot0` | Клиент — parent; ожидается исходный held parent. Совпадение с двумя live brackets, HELLO294/ACK311 bytes, принятый STOP16; 112 debug events |
| `expected_child_slot1` | Клиент — тот же тип parent; ожидается исходный held child. Фактическое различие peer после двух births, первый stage105 / Win32 error5, HELLO0/ACK0, native auto-stop; 92 debug events |
| Оба terminal результата | phase8, retired1, revoked1, authenticated0; IO pending0, producer pending0, IO terminal1, handles0, unknown0, cleanup error0, grants0; по два EXIT125 |
| Внешнее удержание входов | Root проверенно закрыл все 38 freeze handles после завершения hosts/producers |

Числа 112/92 — наблюдённые размеры прежних журналов, а не обязательное число событий любого будущего Windows запуска. Отрицательный control считается подтверждённым по реальному wrong-peer105/5 и двум live brackets. NOT_READY или общий ACCESS_DENIED такого доказательства не дают.

## Как повторить controls

Публичный сценарий теперь размещён в этом каталоге: [инструкция воспроизведения](REPRODUCING.md). Он использует принятый трёхчастный harness, отдельный compiler helper и реальные записи независимого Source-ревью. Fixtures отдельно не запускаются как проверка receiver.

3 октября 2026 года Root исполнил публичный CLI с новой сборкой и двумя свежими hosts: positive HELLO/ACK и negative wrong-peer105/5 прошли, все 45 внешних freeze handles проверенно закрыты. Это новый запуск публичных исходников; исторические частные controls с 38 handles сохранены отдельно. Исходные имена, размеры и SHA256 перечислены в [source_provenance.json](source_provenance.json). При другой раскладке файлов требуется независимое ревью точного переноса путей; ослабление checks для обхода новых хешей не является переносом.

Каждый case получает новый host, контексты, pipe, generation/cookie/instance/nonce/run и каталоги. SID берётся из фактического собственного TokenUser; native повторно проверяет его. Входы и предки каталогов удерживаются до effects. `sourceCopyPin` — измеренный SHA именно parent fixture. Собранные DLL и JSON receipts хранятся в собственном каталоге результатов вне репозитория; их имена не переиспользуются.

Дедлайны original run4000/closure2500 ms не продлеваются. Все debug операции и receiver IO обслуживает один исходный worker. STOP16 сначала отзывает допуск. CancelIoEx не доказывает terminal IO: наблюдаются завершение IO и producers, исходные EXIT/Job и внешний join. `rwr_final_status` читается после actual worker return и внешнего join; ожидаемый первый P105/5 остаётся в raw полях. При UNKNOWN backing storage, OVERLAPPED, buffers и handles удерживаются; успешная уборка не выдумывается.

Проверка сохраняет raw outputs до assertions. Предыдущие отказы остаются отдельными запусками: отказ путей до hosts и отказ v3 после HELLO/ACK из-за phase8→7. Новые PASS используют новые directories и не заменяют эти результаты.

## Источник доказательств и следующий шаг

[Подробный опубликованный результат Root](https://github.com/DmitrL-dev/1cai-public/pull/59#issuecomment-5967283002) описывает текущие частные controls, исправления и открытые границы. Root IQ: 9742 bytes / SHA256 `5e81adb9de2a39eecfc13832bac4cbd060e103729a48cc0150b655cb5c65166a`. Фактическая DLL: 93371 / `29ef433000f796f9c757ca75215cb6d9c4e7a7e427f35b680250731eadaf4e71`.

Main59 CI metadata4/56, accepted Source59 tree, GCC/data ABI, два private transport controls и LiveApply38 имеют отдельные доказательства. Следующий этап — реальный Main boundary и связь его жизненного цикла с original native birth, затем causal role/private factory/EditorEntry/OwnerIPC. Транспортный ACK этих ролей не выдаёт; D8 остаётся OPEN.
