# Первый запуск

Поддержанный профиль: Windows x64 и установленный CPython 3.11.
Для просмотра и создания черновиков платформа 1С не требуется; нужна папка
выгрузки конфигурации. Начните с копии небольшого проекта.

## 1. Установить ядро

В [релизах](https://github.com/DmitrL-dev/1cai-public/releases) выберите
`core-v0.1.0-dev7` и скачайте `rentgen-core-0.1.0.dev7-windows-py311.zip`.
SHA256 архива:

```text
660fe8e7b02169f58a73bb2224c9fcf15f347438b04a6555a62f61f787fe7dc2
```

Проверьте `Get-FileHash .\rentgen-core-0.1.0.dev7-windows-py311.zip -Algorithm SHA256`.
Распакуйте архив в новый каталог и откройте PowerShell внутри папки
`rentgen-core-0.1.0.dev7-windows-py311`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --only-binary=:all: --require-hashes --find-links . --find-links .\wheels -r .\mcp-requirements.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\rentgen.exe --help
.\.venv\Scripts\rentgen-mcp.exe --help
```

Установка использует файлы из архива. В нём есть wheel, исходники ядра,
scanner, зависимости MCP, лицензии и контрольные суммы. Python, редактор,
модель и Java/BSL-LS устанавливаются отдельно.

## 2. Создать проект

Создайте `C:\RentgenState`; замените `C:\MyConfiguration` существующей папкой
выгрузки. Пути registry и state должны быть новыми.

```powershell
New-Item -ItemType Directory -Path C:\RentgenState
$rentgenCommand = (Resolve-Path .\.venv\Scripts\rentgen.exe).Path
& $rentgenCommand registry-init --registry C:\RentgenState\registry.sqlite3
& $rentgenCommand project-register --registry C:\RentgenState\registry.sqlite3 --source-root C:\MyConfiguration --state-root C:\RentgenState\project --name 'Мой проект'
```

Скопируйте `project_id` из JSON-ответа и выполните захват согласно
[инструкции CLI](docs/product/CORE-INSTALLATION.md#первый-проект).
Реестр и состояние остаются локальными; новый снимок не перезаписывает старый.

## 3. Подключить редактор

Скачайте исходники этого репозитория или выполните:

```powershell
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public
```

Следуйте [инструкции профиля VSCodium / Cline](integrations/open-editor/README.md).
Она фиксирует версии и хэши редактора и Cline, готовит отдельные настройки
и собирает companion из исходников. Один VSIX без профиля недостаточен:
расширению нужны Python, registry и ID проекта.

Готовый companion `0.1.4` также есть в релизах; SHA256:

```text
84320dfb9bc1ff512e653688853c6a90aad43fb9654c4c0fca3473c19d927da5
```

## 4. Проверить результат

Откройте дерево «Рентген: модули», выберите модуль и убедитесь, что видите
текст опубликованного снимка. Для правки используйте отдельный черновик.
Его история и сравнение доступны в дереве «Рентген: черновики».

Для команды локальной правки установите BSL runtime по инструкции профиля
и заранее загрузите модель в Ollama. Сохраняемый журнал содержит код и
инструкцию: учитывайте это при передаче диагностических материалов.

Отдельные инструкции: [управляемая правка](docs/product/LOCAL-REPAIR.md),
[права проекта](docs/product/PROJECT-ACCESS.md),
[миграция состояния](docs/product/STATE-MIGRATION.md).
