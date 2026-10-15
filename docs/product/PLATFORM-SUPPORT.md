# Платформы и границы поддержки

Срез публичной поставки: **Core dev19 / Companion 0.1.20**. Полная платформонезависимость —
направление разработки. Поддержка определяется конкретной операцией и
проверенным пакетом, а не языком реализации или расширением установочного файла.

## Что доступно сейчас

| Уровень | Windows | Linux / macOS |
| --- | --- | --- |
| Опубликованные Core dev19 / Companion 0.1.20 | Ранний доступ, Windows x64 / CPython 3.11, ограниченные проверенные сценарии | Linux x86_64: отдельное экспериментальное дополнение для state/history/planners, Rust ZIP import и read-only GUI с поиском и сравнением ZIP. Полный Linux/macOS-маршрут не принят |
| Проверенный development main `413cc65` | Отдельный CI и installed editor API first/restart приняты; human GUI/native 1С открыты. Это не новые опубликованные пакеты | Linux reader/LiveTree и прежний state/ZIP/GUI scope имеют отдельный CI; macOS продукта не принят |
| Проверенный PR #102 source `366db69` | Windows regression, installed editor API и GUI проверены в [scope записи](evidence/development-ci-366db69-20261016.json); без новой native 1С/human приёмки | Linux/amd64 новый private project/default base source+graph capture/publication/history: actual Linux/source SDK и installed CLI проверены. Main `2e2dd4f` имеет то же дерево; fresh push CI отдельно. Offline installed SDK, metadata/drafts/diff/native/live/macOS закрыты |
| Следующий source-кандидат offline CLI/MCP | Принятый Windows-профиль не меняется | Отдельный `owned-linux-cli-mcp-py311-x86_64-v1`: CPython 3.11.15 / x86_64, glibc ≥ 2.34 / kernel ≥ 5.9 и 29 locked SDK wheels; результат actual offline/SDK-приёмки — только в отдельной проверенной `acceptance.json` точных source/bytes. Python 3.12 — source/CLI CI, без SDK offline closure |
| Захват, снимки и граф в опубликованном Core | Windows retained-file sessions и доверенный scanner | Безопасные адаптеры чтения/захвата ещё нужно принять |
| BSL/1С/EDT, live apply, Observer-служба | Свои runtime, права и ограничения; не универсальное применение | Не включаются автоматически вместе с переносимым CLI |
| VSCodium / Cline / Companion | Текущий профиль требует Windows и доверенную рабочую папку | Наличие самого редактора на ОС не переносит интеграцию Рентгена |

Подтверждённая опубликованная пара:
[Core dev19](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev19) /
[Companion 0.1.20](https://github.com/DmitrL-dev/1cai-public/releases/tag/companion-v0.1.20).
[Состояние и история проверок](https://github.com/DmitrL-dev/1cai-public/blob/main/docs/product/READINESS.md) сохраняют связь с фактическим выпуском.

## Экспериментальное Linux-дополнение Core dev19

Linux уже имеет отдельный [CLI/state/history режим](PORTABLE-CORE.md) и
[экспериментальный Rust ZIP import](RUST-INPUT-CORE.md). Последний анализирует
переданные immutable bytes, не создаёт published snapshot и не открывает live apply.
[Локальный GUI](LOCAL-GUI.md) использует эти байты для поиска, чтения, двух/трёх
ZIP и ограниченного line diff; установка описана в `INSTALL.md` финального архива.
macOS пока получает только capability report; его identity/IO adapters не приняты.
Companion по-прежнему использует Windows-профиль. Дополнение опубликовано в
[Core dev19](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev19)
с отдельными manifest и SHA256SUMS. Оно содержит Python wheel и Rust executable,
но не MCP-зависимости, Go scanner или редактор; это не полный офлайн-комплект.
Нужны GNU/Linux x86_64, glibc 2.34+, `libgcc_s.so.1`, kernel 5.9+, memfd sealing
и `/proc/self/fd`. [Проверка компонентов](../../releases/core/0.1.0.dev19/qualification.json)
и [проверка публичных файлов](evidence/release-dev19-publication-20261015.json)
относятся к точным байтам; новая native 1С/редакторная приёмка не заявляется.

Полный Linux regression не является зелёным: прежние retained-Windows и
platform-fixture отказы учтены отдельно от целевых portable tests. Старые Windows
результаты на другом candidate не переносятся на эту сборку.

## Проверенный capture source и следующий offline-кандидат

[Linux capture и retained source/graph](PORTABLE-CORE.md#linux-capture-и-чтение-снимков)
приняты в ограниченном scope на [PR #102, HEAD `366db69`](evidence/development-ci-366db69-20261016.json):
Linux/amd64 новый private project/default base, trusted static Go scanner с SHA-256,
complete generation, publication receipt и история. Actual Linux/source SDK и
installed CLI проверены отдельно; они не квалифицируют offline installed SDK.
Main `2e2dd4f` имеет то же дерево, его fresh push CI — отдельная проверка.
Defaults 64 МиБ total / 16 МиБ file / 4096 entries не являются приёмкой максимального
workload или полного B07. Этот маршрут не входит в dev19; его PR receipt
не переносится на последующие source/bytes, macOS или полный продукт.

[CI main `413cc65`](evidence/development-ci-413cc65-20261016.json) относится к
предыдущему development-срезу, включая настоящий Windows editor API workbench,
прежний Linux state/ZIP/GUI и synthetic diagnostic framework. Он не переносится
на новые capture bytes, human GUI, native 1С или AI competence.

Для следующей доставки есть отдельный source-кандидат [Linux CLI/MCP offline kit](../../scripts/release/OWNED-LINUX-KIT.md)
и [его SDK lock](../../requirements/locks/LINUX-MCP-LOCK.md). Подготовка/проверка
входных bytes не заменяет новую установку финального архива на точном target.
CI capture и опубликованный dev19 не квалифицируют этот новый offline-профиль.

## Как станет проще работать на разных ОС

1. Отделить доверенную локальную идентичность и доступные операции от Windows.
2. Открыть ограниченные операции локального состояния и чтение истории черновиков.
3. Принять адаптеры безопасного чтения сохранённых снимков на Linux и macOS.
4. Добавить захват, запуск анализаторов, отмену и воспроизводимую поставку по ОС.
5. Только после этого рассматривать перенос записи в живые исходники.

Доступность должна быть видна пользователю: операция доступна либо объясняет,
какой адаптер/условие отсутствует. Отказ происходит до побочных эффектов.
Поддержка CLI, MCP, редактора, native-инструментов и службы проверяется отдельно.
Успешный импорт Python-модуля или `--help` не является такой проверкой.

## Что сохраняется при переносе

- Права определяются доверенной идентичностью ОС, а не именем из запроса модели.
- Windows SID и существующие контракты состояния не меняются молча.
- Локальный UID другой машины не даёт права на перенесённый проект.
- Хэши, ожидаемая ревизия, квитанции, миграция и восстановление остаются частью контракта.
- Успех модели, BSL или тестов не разрешает запись. Неизвестный исход не становится успехом.
- Гарантии файлов и процессов заявляются отдельно для каждой ОС.

## Rust и производительность

Первый Rust input core уже выполняет bounded import и владеет byte session
в отдельном Linux процессе. Он поставляется в экспериментальном дополнении
Core dev19; это не полный Rust Core. Измерения synthetic corpus и parity tests не являются обещанием
универсального ускорения. Python-компоненты и Go scanner сохраняют свои роли.

[Порядок работ и приёмка](https://github.com/DmitrL-dev/1cai-public/blob/main/ROADMAP.md) ·
[Архитектура](https://github.com/DmitrL-dev/1cai-public/blob/main/ARCHITECTURE.md)
