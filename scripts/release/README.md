# Выпуск компонентов Рентгена

`main` содержит продуктовый код. Пакеты выпускаются отдельными тегами:
`companion-v<версия>` и `core-v<версия>`. Принятые выпуски перечислены в
[README](../../README.md) и [GitHub Releases](https://github.com/DmitrL-dev/1cai-public/releases).
Тег и уже опубликованные байты не
перезаписываются. Полная готовность продукта отдельным тегом не заявляется.

## Проверка обещаний перед публикацией

- Указать точный исходный commit, версию, ОС и принятые сценарии.
- Перепроверить CI именно этого commit, установку готовых файлов и совместимость пары.
- Разделить Windows-выпуск, ограниченные portable-операции и экспериментальный Editor.
- Сверить README, Pages (если опубликованы), About, package description и release notes
  с [состоянием поставки](../../docs/product/READINESS.md) и
  [платформами](../../docs/product/PLATFORM-SUPPORT.md).
- Не объявлять ускорение без сопоставимых замеров, Linux/macOS без отдельных проверок
  или качество AI по одному искусственному примеру.
- Сохранить старые release notes, manifests и assets. Новый доставляемый README
  или описание тоже меняет байты пакета и требует новой квалификации.
- После публикации проверить публичные ссылки и хэши скачанных файлов.

Исходники кандидата, выбранный будущий номер версии и локальный тест не являются
новым релизом. Опубликованная пара — Core dev19 / Companion 0.1.20;
[квитанция публичных файлов](../../docs/product/evidence/release-dev19-publication-20261015.json)
связывает её публичные байты и теги; CI и installation/interop/browser сохраняет
[Core qualification](../../releases/core/0.1.0.dev19/qualification.json).
Следующие исходники требуют своей приёмки;
[план и незакрытые направления](../../docs/product/RELEASE-PLAN-20261015.md)
ведутся отдельно от опубликованных пакетов.

Для будущей полной поставки есть отдельный read-only
[аудит плана кандидата v2](RELEASE-PLAN-CONTRACT.md): явные channel/source/tree,
component pair, exact bytes, dependency/license inventory и lifecycle coverage.
Он сохраняет все 127 требований, IDE24 и Windows/Linux/macOS final targets;
отсутствующие native/model/human/product adapters остаются unqualified.
Результат всегда `published:false`, не является qualification receipt и не
включает stable publication. Существующие prepare/verify workflows не изменены.

Экспериментальное Linux-дополнение готовится по
[отдельной инструкции](EXPERIMENTAL-LINUX.md). Помимо CLI, для нового GUI
нужны smoke установленного wheel с настоящим loopback HTTP/Rust и все
43 браузерных gates без пропусков, выполняемые над установленным пакетом.
Наличие этого маршрута в CI не является результатом: перед выпуском нужны
успешный запуск точного source commit и проверка извлечённых финальных байтов.

## Companion

В `releases/companion/VERSION` фиксируются проверенный SHA256/размер VSIX и
заметки для пользователя. Выполняйте команды из корня чистого checkout с
закоммиченными входами и записью принятой версии. Версия тега должна точно
совпадать с `integrations/vscode-rentgen/package.json`:

```powershell
$companionVersion = (Get-Content -Raw integrations/vscode-rentgen/package.json | ConvertFrom-Json).version
$companionTag = "companion-v$companionVersion"
py -3.11 scripts/release/prepare_companion.py build --tag $companionTag --output NEW_COMPANION_DIRECTORY
py -3.11 scripts/release/prepare_companion.py verify --tag $companionTag --output NEW_COMPANION_DIRECTORY
```

Замените `NEW_COMPANION_DIRECTORY` путём к новому каталогу. `build` собирает
VSIX, сверяет его с принятым хешем и создаёт SHA256SUMS/release.json;
`verify` заново проверяет пакет, заметки, состав каталога и commit provenance
без пересборки. Для проверки уже опубликованного Companion используйте checkout
его тега: `release.json` привязан к конкретному HEAD. Более поздний commit
документации может содержать тот же VSIX, но другой provenance. Он не заменяет
метаданные опубликованного выпуска.

Workflow `release.yml` реагирует только на `companion-v*`: выполняет тесты
расширения на Windows, собирает принятые байты и отдельно перепроверяет скачанный
артефакт перед созданием GitHub Release. Результат — draft/prerelease, с
запретом Latest и перезаписи файлов. Непрошедшие проверки не пропускаются.
Это проверка компонента; она не заменяет платформенные тесты или оценку качества AI.

Собранный VSIX содержит собственные исходники и сборщик. Заметки берутся из
проверенного файла версии, а не из полной истории рабочего репозитория.
Параметры публикации: [action-gh-release](https://github.com/softprops/action-gh-release).

## Core

Принятый ZIP берётся из успешного CI для точного `source_commit` манифеста.
До подготовки выпуска проверяются GitHub digest артефакта и офлайн-установка
через `scripts/verification/verify_core_kit.py` с внешним SHA256.

```powershell
$coreVersion = py -3.11 -c "import pathlib,tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
py -3.11 scripts/release/prepare_core.py prepare --version $coreVersion --kit PATH_TO_ACCEPTED_KIT.zip --output NEW_CORE_DIRECTORY
py -3.11 scripts/release/prepare_core.py verify --version $coreVersion --output NEW_CORE_DIRECTORY
```

Замените `PATH_TO_ACCEPTED_KIT.zip` путём к принятому CI-архиву данной версии,
а `NEW_CORE_DIRECTORY` — путём к новому каталогу. Версия берётся из текущего
`pyproject.toml`; до запуска для неё должны быть приняты и закоммичены
`releases/core/VERSION/manifest.json` и `RELEASE_NOTES.md`. Само изменение
номера версии не означает, что соответствующий релиз принят.

Команды сверяют принятые SHA256/размер, исходный коммит внутри комплекта,
wheel/sdist и точный состав файлов выпуска. Манифест и заметки должны быть
закоммичены. Тег core указывает на `source_commit` сборки; записи выпуска
фиксируются позже, поскольку SHA256 архива зависит от встроенного коммита.
Поэтому подготовку Core выполняют из checkout с закоммиченной записью выпуска
и доступным в истории `source_commit`; сам исходный Core-тег может ещё не
содержать манифест, добавленный после приёмки его сборки.
Нельзя подменять принятый ZIP сборкой последующего коммита документации.
Публикуются ZIP, manifest.json, SHA256SUMS и RELEASE_NOTES.md как prerelease.

## Финальная Linux-квалификация кандидата

После обычного merge и успешных **main push** runs точного исходного SHA
запустите read-only workflow [release-candidate-ci.yml](../../.github/workflows/release-candidate-ci.yml):

```sh
gh workflow run release-candidate-ci.yml --repo DmitrL-dev/1cai-public --ref main \
  -f source_sha=EXACT_MAIN_SHA \
  -f product_run=PRODUCT_RUN_ID \
  -f portable_run=PORTABLE_RUN_ID
```

Подставьте SHA и run IDs `Product checks` / `Experimental portable contracts`
одного commit. Workflow проверяет GitHub artifact digests до распаковки, Windows
kit provenance и полное содержимое wheel обеих ОС. ZIP container metadata может
различаться; доставляется неизменный канонический wheel Windows-комплекта.
Из него и Linux CI helper собирается supplement, затем именно его извлечённые
байты проходят установленный CLI/HTTP/Rust и все 43 sandboxed browser gates.
Токен GitHub доступен только сбору входов, не выполнению пакета.

Результат — CI artifact с тремя файлами кандидата и ограниченными квитанциями.
Workflow не создаёт теги, не принимает manifests, не публикует Release и не
заменяет отдельную проверку Windows/native/Companion. После успешной квалификации
зафиксируйте фактические records и выполните штатный `prepare/verify`;
публикуйте те же проверенные байты. При ошибке кандидат не считается принятым.

## Общие заметки и локальные теги

`create_release.py --version v1.2.3` только готовит RELEASE_NOTES.md. Текущий тег
исключается из выбора предыдущего; повторная генерация заменяет раздел той же
версии, сохраняя историю. Перед публикацией заметки нужно проверить и закоммитить.

`--tag` создаёт аннотированный тег текущего HEAD только при чистом worktree и
закоммиченном разделе этой версии. Он не генерирует новые заметки за спиной
оператора. `--push --remote NAME` отправляет только указанный тег в явно выбранный
remote, без force. При отказе сервера тег может уже существовать локально:
проверяйте его и повторяйте адресный `git push`, не создавайте новый тег вслепую.

Make-цели `release-notes`, `release-tag`, `release-push` теперь отдельные;
для последней обязательны VERSION и REMOTE. Общие теги `v*` больше не запускают
автоматический выпуск всего продукта. Работа с core-комплектом проходит отдельную
проверку wheel/sdist/scanner/lock и установленной версии.

## Политика готовых блоков и выпусков

Готовый блок — завершённый проверенный пользовательский сценарий в явно
указанном scope: функциональность, необходимые проверки и актуальные инструкции
дают заявленный результат, ограничения остаются видимыми. Такой блок проходит
одним логическим PR. Мелкие checkpoints сохраняются локально; на рабочую ветку
можно отправлять проверочные commits/draft PR, когда remote HEAD необходим
для Windows/Linux CI или ревью. Незавершённость проверки не выдаётся за готовность.

Независимый готовый PR по умолчанию сливается squash одним итоговым коммитом.
Обычный merge используется для сохранения нужной цепочки зависимых PR либо
по явному указанию человека. После изменения итогового source SHA требуемые
integration/release gates выполняются заново. Опубликованные коммиты, теги,
release notes и assets не переписываются ради новой формы истории.

Выпуск собирает несколько готовых блоков в совместимый milestone Core/Companion;
каждый PR не требует собственного bump/tag. Версия повышается только у
компонента с доставляемыми изменениями. Неизменённый принятый компонент остаётся
на прежней версии, а совместимость конкретной пары проверяется отдельно.
Наличие нового Core не даёт автоматического допуска неизвестных версий в Companion.

Provenance требует честного порядка: сначала фиксируется исходный commit и
получаются точные bytes, затем после их проверки — qualification records,
manifests и checksums. После публикации и анонимной загрузки появляется
publication receipt с реальными тегами, размерами и SHA-256. Это минимальные
служебные записи; их нельзя фабриковать раньше факта ради одного коммита.
Объединяйте post-release evidence и актуализацию README/инструкций/сайта в один
PR с одним итоговым коммитом. Уже принятые сборки сохраняют свои source/tag SHA;
последующие записи не подменяют доставленные bytes.

Текущий milestone dev19 / Companion 0.1.20 объединяет проверенные изменения
после dev17, включая ручные черновики и экспериментальный Linux GUI.
Source-facts PR #84 остаётся отдельно и не входит в этот выпуск.
Новая политика не отменяет квалификацию и выпуск dev19 и не требует переписывать
историю PR #99. Следующие блоки и выпуски следуют правилам выше.
