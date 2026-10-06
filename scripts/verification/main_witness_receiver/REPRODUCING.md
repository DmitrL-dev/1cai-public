# Воспроизведение двух проверок приёмника

Эта инструкция предназначена для разработчика или ревьюера экспериментального Windows-приёмника. Для установки и обычной работы с Рентгеном откройте [первый запуск](../../../GETTING_STARTED.md).

`reproduce.py` собирает новую диагностическую DLL, проверяет её интерфейсы и запускает два отдельных тестовых процесса. Первый опыт проверяет ожидаемый parent, второй намеренно ожидает child при подключении parent. Во втором опыте должен сохраниться именно отказ wrong-peer105/5; общий отказ или NOT_READY успешным результатом не считаются.

## Что нужно подготовить

- Windows x64; Python x64 **3.11.9**, Node **24.15.0** и проверенный GCC x64.
- Полную копию репозитория и существующий отдельный каталог для результатов вне этой копии.
- Настоящие записи независимого Source-ревью с размерами, SHA256 и путями трёх native исходников, трёх harness helpers и compiler helper. Их содержание не создаётся CLI.
- Полное чтение исходников оператором и отдельное решение о допуске компиляции и двух controls.

CLI сверяет точные байты девяти входных исходников и образы Python/Node. Compiler helper сверяет GCC: `3020288` bytes, SHA256 `690d171db384af0f69002374a7fc4755128ee82c688d22818bd981f869a65890`. Пины Python/Node и исходников перечислены непосредственно в `reproduce.py`; новые или изменённые образы требуют нового рассмотрения исходников и допустимых входов.

Compiler helper ожидает GCC именно по пути `C:\mingw64\bin\gcc.exe`.
Node вне каталога исходников или результатов должен находиться по пути
`C:\Program Files\nodejs\node.exe`, который допускает внешний helper.
Произвольные версии инструментов и свободный перенос их установки этим
зафиксированным сценарием не поддерживаются.

Одна совместная запись ревью может быть передана в оба review flags, если она действительно покрывает native и harness файлы. Для compiler helper поддерживаются поля `compiler_helper_ref`, `current_compiler_helper` или `compiler_helper`. При изменении абсолютных путей требуется отдельная настоящая запись независимого ревью переноса: schema `rentgen-reviewed-main-receiver-source-relocation/1`, scope `source-path-relocation-only`, неизменные байты и точные новые пути. Её формат описан в проверках `reproduce.py`. Простого изменения путей в старой принятой записи недостаточно.

## Команда для PowerShell

Замените пути и SHA на свои фактические входы. Перед выполнением прочитайте перечисленные исходники и записи ревью. Каталог `$receiverEvidence` должен уже существовать и находиться вне `$receiverSource`.

```powershell
$receiverSource = 'E:\Rentgen'
$receiverEvidence = 'C:\RentgenEvidence'
$receiverPython = 'C:\Python311\python.exe'
$receiverNode = 'C:\Program Files\nodejs\node.exe'
$receiverReview = 'C:\RentgenEvidence\accepted-source-review.json'
$receiverReviewSha = (Get-FileHash -LiteralPath $receiverReview -Algorithm SHA256).Hash.ToLowerInvariant()

& $receiverPython -I -S -B -X utf8 -u `
  "$receiverSource\scripts\verification\main_witness_receiver\reproduce.py" `
  --source-root $receiverSource --evidence-root $receiverEvidence `
  --python $receiverPython --node $receiverNode `
  --native-review $receiverReview --native-review-sha $receiverReviewSha `
  --harness-review $receiverReview --harness-review-sha $receiverReviewSha `
  --Root-full-source-read --admit-compile --admit-controls

if ($LASTEXITCODE -ne 0) { throw 'Проверка не принята. Сохранённые результаты оставьте для разбора.' }
```

При настоящем независимом переносе путей добавьте `--relocation-review` и `--relocation-review-sha`. Если две исходные записи ревью раздельные, передайте каждую в соответствующий flag со своим SHA.

Без трёх decision flags сценарий только измеряет входы и сохраняет подготовленные данные. `--Root-full-source-read` — заявление оператора о выполненном чтении, `--admit-compile` допускает сборку и чтение data ABI, `--admit-controls` отдельно допускает два опыта. Последний flag требует первые два. Эти flags отражают решение оператора; они не выдают продуктовых полномочий.

## Какие результаты сохраняются

Каждый вызов создаёт новый каталог `public-main-receiver-reproduction-<UUID>`. Старые результаты сохраняются. В новом каталоге будут:

| Файл или группа | Что фиксирует |
|---|---|
| `measured-inputs-and-operator-decisions.json` | Реальные пути, размеры, SHA, записи ревью и решения оператора |
| `compile-admission.json`, `compile-helper-raw-before-checks.json` | Допуск и фактический код возврата, stdout/stderr компиляции |
| `Root-reviewed-Main-receiver-compile-<UUID>/` | Новые снимки исходников, DLL и фактически прочитанные RLD12/RWR13 ABI |
| `two-controls-request.json`, `two-controls-helper-raw-before-checks.json` | Допуск и фактические результаты вызова harness |
| `Root-Main-receiver-two-new-cases-<UUID>/` | Два новых seed/config, SID, freeze records, raw host outputs и checks каждого case |
| `operator-reproduction-result.json` | Ссылки на сохранённые результаты после успешного возврата обоих этапов |

Raw данные сохраняются до проверок результата. Каждая сборка и каждый из двух hosts вызываются один раз; автоматического повторения не предусмотрено. При отказе итогового файла может не быть: изучайте raw records и stderr в созданном каталоге.

## Выполненный запуск 3 октября 2026 года

Root исполнил CLI публичного каталога с SHA256 `ad123d13d1367d717a2e4424f8c7b578edab42dc0dc3d9978d8ac18e910b5b97`. Новая DLL: `93327` bytes / SHA256 `4da7a7aecb99a1d4f9a109745f475ad10f3f8682ae473b7917bc503efda521f4`. Компиляция завершилась с кодом0 и пустыми stdout/stderr; фактически прочитаны оба ожидаемых data ABI.

| Опыт | Наблюдение |
|---|---|
| Ожидаемый parent | Kernel peer совпал с original held parent; оба live brackets; HELLO294/ACK311 bytes; 112 debug events; выполнен STOP16 |
| Ожидаемый child при подключении parent | Kernel peer отличался от original held child; оба live brackets; first-P105 / error5; HELLO0/ACK0; 92 debug events; native auto-stop |
| Завершение обоих опытов | Worker вернулся и присоединён; Job пуст; по два EXIT125; receiver phase8/retired1/revoked1/auth0/IO0/producer0/terminal1/handles0/unknown0; cleanup error0 |
| Удержание входов | Все 45 freeze handles — 24 файла и 21 каталог — проверенно закрыты |

112/92 и 45 — наблюдения этого запуска. Проверки опираются на контракт lifecycle, IO и принадлежности peer; количество debug events и предков каталогов зависит от конкретного опыта. Исторические частные controls с 38 handles описаны отдельно в [README](README.md).

Этот опыт подтверждает два synthetic transport controls публичных исходников. Настоящий Main редактора, EditorRole, OwnerIPC и ежедневная работа с моделью и задачей ещё требуют своих проверок. D8 остаётся OPEN; полная готовность нового выпуска этим опытом не установлена.

## Проверки исходников в CI

`tests/unit/test_main_witness_reproduction_contract.py` проверяет точные
размеры и SHA опубликованных исходников, согласованность ABI, безопасный
`--help`, строгий разбор конфигурации и предикаты terminal/negative-case.
Тестовые записи специально синтетические: проверяются как допустимые поля,
так и отказы при неверной идентичности, незавершённых IO, worker или handles.

Эти тесты не компилируют DLL и не исполняют Windows controls. Зелёный общий
CI подтверждает свои перечисленные проверки; числа 112/92/45 выше остаются
историческим результатом 3 октября 2026 года. Для новой native-квалификации
нужен отдельный запуск CLI с настоящими входами и записями ревью.
