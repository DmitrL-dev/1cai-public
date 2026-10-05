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
новым релизом. Сами по себе они не меняют статус опубликованного dev15.

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
