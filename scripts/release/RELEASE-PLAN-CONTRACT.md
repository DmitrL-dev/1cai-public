# Локальный аудит плана кандидата

`scripts/verification/verify_release_plan.py check` проверяет явный план будущей
поставки и локальные bytes. Он не выполняет команды из квитанций, не собирает
пакеты, не обращается к сети, не меняет Git, не создаёт qualification records,
теги или Release. Старые `prepare_core`, `prepare_companion`, экспериментальная
Linux-поставка и draft/prerelease workflow сохраняют свои контракты.

```sh
python scripts/verification/verify_release_plan.py check \
  --plan /canonical/path/plan.json \
  --evidence-root /canonical/path/evidence \
  --repository /canonical/path/source-checkout
```

В stdout поступает один детерминированный JSON без времени и абсолютных путей.
Код 1 означает ошибку контракта или bytes; код 2 — корректный, но неполный аудит.
Код 0 зарезервирован для полной квалифицированной coverage; текущая реализация
его не достигает: product adapters и stable packaging ещё отсутствуют.
`published:false` и `qualification_receipt:false` действуют всегда.
`contract_valid:true` не означает принятую поставку.

## Закрытый план v2

Все объекты имеют ровно перечисленные поля; неизвестные поля запрещены.

* `schema`: `rentgen-release-plan/2`.
* `channel`: `development`, `release-candidate` или `stable`. Для Core версии
  имеют соответственно вид `X.Y.Z.devN`, `X.Y.ZrcN`, `X.Y.Z`; теги —
  `core-vX.Y.Z-devN`, `core-vX.Y.Z-rcN`, `core-vX.Y.Z`.
  Companion — `X.Y.Z`, `X.Y.Z-rc.N`, `X.Y.Z` и префикс `companion-v`.
  Числа канонические, N положительное; stable не выводится автоматически.
* `source_commit`, `source_tree`, `record_commit`: точные lowercase SHA-1.
  Git проверяет существующий source commit/tree, ancestry source → record → HEAD
  и версии из committed `pyproject.toml` / `package.json`. Record и source
  сохраняются раздельно. Checkout может быть более поздним; его bytes не
  подменяют source. Унаследованные `GIT_*` не меняют выбранный repository,
  replacement objects и lazy fetch отключены.
* `components`: ровно `core` и `companion`, каждый с `version` и `tag`.
* `component_pair`: ровно `core` и `companion` с теми же точными версиями.
* `assets`: массив `{id, kind, component, os, arch, blob}`. Требуется ровно по
  одному asset на каждый уникальный component/OS/arch/kind из каталога.
  Это проверка declared inventory и bytes, а не новый парсер форматов пакетов.
* `dependencies`: массив `{id, version, distribution_sha256, license,
  license_file}`. Version и digest закреплены; `license_file` связан с реальными
  bytes. Все declared dependencies должны использоваться в deliveries.
  Полнота транзитивного inventory и корректность лицензирования требуют
  отдельного adapter/review: произвольный непустой список их не доказывает.
* `deliveries`: массив `{component, os, arch, runtime, operation, asset,
  dependencies, cells}`. Asset и dependency IDs должны существовать и иметь
  нужный scope. `cells` отображает lifecycle name в `{status, receipt}`.
* `requirements`: массив `{id, status, receipt}` для canonical IDs каталога.
  Пропущенный ID остаётся missing. Не допускаются неизвестные и повторные IDs.

`blob` и `license_file` имеют вид `{path, sha256, size_bytes}`. Это относительный
путь внутри evidence-root, SHA-256 и положительный целый размер. Пустые файлы,
symlinks/reparse points, traversal, alternate separators, повторные JSON-поля,
non-finite/float values и bool вместо integer запрещены. В evidence-root
должны быть ровно все используемые assets, license files, receipts и их raw
attachments, без лишних файлов. Plan хранится снаружи evidence-root.

## Каталог и coverage

`release_policy.json` — конечная reviewed policy, а не вход автора плана.
Её 127 IDs проверяются по canonical fingerprint и полному реестру
`FULL-FINAL-PLAN.md`; все 24 `IDE-SC-*` обязательны. Удаление строки одновременно
из обоих документов не сокращает цель. Изменение требований требует отдельной
осознанной правки policy и fingerprint.

Текущий реализованный lifecycle-аудит требует 35 cells: Windows x64 Core
CPython 3.11 CLI/MCP; Windows x64 Companion VSCodium 1.135.06055 editor;
Linux x86_64 Core CPython 3.11 CLI/GUI. Для каждой tuple обязательны
`dependencies`, `offline-install`, `update`, `uninstall`, `state-migration`,
`cancel`, `recovery`. Это конечный audit scope, а не объявление поддержки.
Новые runtime/OS/arch/operations требуют reviewed policy.

**Полная цель шире этих пяти tuples.** Отдельно обязательны Windows/Linux/macOS
IDE client и executor, каждый со своей архитектурой, toolchain и topology.
Их полная qualification пока не реализована; все шесть `final-target/*` видны
как unqualified. Linux subset не удаляет macOS из цели. Все 127 полных критериев,
включая native 1С/EDT, model и human evidence, остаются отдельными gates.

Статусы — `passed`, `failed`, `missing`, `not-applicable`. Для missing receipt
строго `null`; passed/failed требуют bytes. В текущем каталоге **нет** approved
N/A tuples: reason string не может выключить обязательный сценарий.
Omitted tuple/cell становится missing; unknown/duplicate tuple — ошибка.

## Typed receipts и граница доверия

Receipt schema `rentgen-release-evidence/1` содержит ровно:

* `kind`: `lifecycle-execution`, `github-main-ci` или `full-product-criterion`;
* `origin`: `fixture` или `execution`;
* `source_commit`, `source_tree`, `component_pair` — совпадают с plan;
* `scope`: для lifecycle ровно `{delivery, lifecycle}`, где delivery —
  `component/os/arch/runtime/operation`; для criterion ровно
  `{requirement, scope:"full-criterion"}`;
* `assets`, `dependencies`: отсортированные точные ID выбранной delivery либо
  всех plan assets/dependencies для full criterion;
* `result`: `{executed, passed, failed, errors, skipped}`, неотрицательные
  целые, executed равен сумме остальных. Для положительного результата нужны
  ненулевые passed, отсутствие failures/errors/skips и нулевой exit code;
* `execution`: для local kinds `{command, exit_code}`; command — непустой
  bounded argv, сохраняемый как claim и никогда не исполняемый этим инструментом;
* `attachments`: непустой список blob references к raw evidence.

`github-main-ci.execution` вместо command имеет ровно `repository`, `workflow`,
`run_id`, `run_attempt`, `artifact_id`, `event`, `branch`, `status`, `conclusion`,
`artifact`. Repository фиксирован на `DmitrL-dev/1cai-public`, разрешены известные
обычные workflows, `push/main/completed`, положительные IDs/attempt и точный
artifact blob. Failure/cancelled не становятся pass. Это локальная проверка
сохранённых metadata/bytes; аутентичность API здесь не удостоверяется заново.
Сетевой collector с API digest/run-attempt остаётся отдельным шагом.

Lifecycle требует kind `lifecycle-execution`; unit/CI wrapper его не заменяет.
`delivery.bound_execution_passed` считает проверенные typed execution claims;
это не криптографическая аттестация того, что произвольный автор запустил argv.
Fixture проходит алгоритм declared coverage и остаётся unqualified. Даже
`origin:execution` / `full-product-criterion` не создаёт authority: для полного
criterion сейчас **нет** admission adapters. Произвольное `accepted:true`
вообще не входит в schema. CI subset, synthetic pilot, installed editor и
native/model/human qualification не взаимозаменяемы.

Report разделяет `contract_valid`, delivery coverage, полную `coverage_complete`
и `stable_eligible`; missing/failed/unqualified перечислены по точным cells.
Отсутствующие full-criterion adapters, dependency-closure adapter и stable
packaging/publication остаются явными B10 gaps. Инструмент не закрывает
`FINAL-STABLE-CHANNEL-01` или `FINAL-DELIVERY-MATRIX-01` и не даёт разрешение
выпустить stable после изменения одного флага.

## Пределы и проверки

JSON/отчёт ≤1 MiB, depth ≤24, nodes ≤30000, string ≤4096 characters;
file ≤256 MiB, inventory ≤1024 entries / 1 GiB; относительный путь ≤240
characters / 8 components; до 32 assets/deliveries, 256 dependencies,
127 requirements, 16 raw attachments на receipt. Git read-only calls ограничены
15 секундами. Файлы хэшируются потоково; JSON читается в пределах своего лимита.
Нужен quiescent evidence-root с canonical absolute ancestors без symlinks.
Identity/stamps до и после чтения обнаруживают замену; это не retained lease
против malicious same-user writer. SHA/size binds прочитанные bytes.

Обычный pytest CI собирает `tests/unit/test_release_plan.py`. Он использует
настоящие временные Git history и files, проверяет tamper/source/scope/counts,
missing/failed/skipped, CLI immutability и невозможность product acceptance
из полной fixture. Это локальные contract tests, не GitHub CI/native приёмка.
