# Рентген Core 0.1.0.dev16 — первый снимок и проверяемая поставка

Предварительная версия Windows x64 / CPython 3.11. Core сохраняет снимки выгруженных исходников 1С, историю черновиков и квитанции
операций, предоставляет команды терминала (CLI) и интерфейс MCP для редактора.

**Предварительный выпуск компонентов.** Финальный комплект проверен офлайн
в новом окружении. Общая готовность продукта: `full_product_ready=false`.

## Что можно получить сначала

Для первого снимка нужны Windows, Python 3.11, готовый комплект Core и папка
выгрузки исходников. Модель, Ollama, Java/BSL Language Server и платформа 1С
для этого шага не нужны. Они требуются только соответствующим дальнейшим
сценариям. Регистрация проекта — отдельный шаг после установки Core.

| Объект | Значение |
| --- | --- |
| Снимок | Сохранённые файлы выгрузки с собственным идентификатором |
| Предложение / черновик | Предлагаемая правка и её сохранённые ревизии |
| Квитанция | Результат операции; помогает разобраться с прерыванием |
| Применение | Отдельная запись в поддержанном сценарии с явным вызовом и проверками |

Снимок не обновляет информационную базу. Сохранение черновика не применяет
его к рабочей конфигурации. Сначала можно прочитать модули и diff.

## Изменения после опубликованного dev15

- Инструкции установки выбирают wheel нужной версии; офлайн MCP-зависимости
  закреплены. Отсутствующий пакет не подменяется чужим старым wheel.
- Source Observer и SCM verification получили ограниченную диагностику
  ожидания capture. Проверки активной фазы, STOP, recovery и cleanup сохранены.
- Cold owner и retained IO проверяются контролируемыми Source-тестами.
  Marker, PID и synthetic frame не разрешают реальный запуск.
- README и руководства объясняют CLI / редактор и путь
  снимок → предложение → версия → проверка → отдельное применение.
  Добавлены цветные SVG-схемы.
- Python CI распределён по трём workers. Ускорение пользовательских
  операций этим не измерено.
- Python application-frame из PR54 — частный verification helper репозитория,
  не входящий в Core wheel. Пользовательский transport он не устанавливает.

Dev15 и Companion 0.1.15 сохраняют собственные теги и исторические свидетельства.

## Установка готового комплекта

1. Скачайте ZIP, `manifest.json` и `SHA256SUMS`. Сверьте SHA256:

   ```powershell
   Get-FileHash -LiteralPath .\rentgen-core-0.1.0.dev16-windows-py311.zip -Algorithm SHA256
   ```

   При несовпадении с manifest остановите установку.

2. Распакуйте в новую папку и перейдите в
   `rentgen-core-0.1.0.dev16-windows-py311` с `wheels`,
   `mcp-requirements.lock` и `bsl-scan.exe`.

3. Создайте отдельное окружение и установите закреплённые файлы комплекта:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --no-index --only-binary=:all: --require-hashes --find-links . --find-links .\wheels -r .\mcp-requirements.lock
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\rentgen.exe --help
   .\.venv\Scripts\rentgen-mcp.exe --help
   ```

   Успех: `pip check` не сообщает конфликтов; команды показывают справку.
   При ошибке разберите её до продолжения.

Python, редактор, Java, модели и 1С в ZIP не входят.
Подробности: [готовый комплект](https://github.com/DmitrL-dev/1cai-public/blob/core-v0.1.0-dev16/docs/product/CORE-OFFLINE-KIT.md)
и [установка Core](https://github.com/DmitrL-dev/1cai-public/blob/core-v0.1.0-dev16/docs/product/CORE-INSTALLATION.md).

## Первый снимок без AI и запуска 1С

В папке комплекта замените `C:\MyConfiguration` существующей папкой выгрузки.
Выберите новую папку состояния: пример не создаёт повторно используемый реестр.

```powershell
New-Item -ItemType Directory -Path 'C:\RentgenState' -ErrorAction Stop
$rentgenCommand = (Resolve-Path .\.venv\Scripts\rentgen.exe -ErrorAction Stop).Path
& $rentgenCommand registry-init --registry 'C:\RentgenState\registry.sqlite3'
& $rentgenCommand project-register --registry 'C:\RentgenState\registry.sqlite3' --source-root 'C:\MyConfiguration' --state-root 'C:\RentgenState\project' --name 'Мой проект'
```

Скопируйте свой `result.project_id` из ответа регистрации. Это идентификатор,
а не отображаемое имя проекта:

```powershell
$projectId = 'ВАШ-PROJECT-ID-ИЗ-ОТВЕТА'
& $rentgenCommand capture --registry 'C:\RentgenState\registry.sqlite3' --project $projectId --scanner .\bsl-scan.exe
```

Из успешного итогового ответа возьмите `result.snapshot.snapshot_id`:

```powershell
$snapshotId = 'ВАШ-SNAPSHOT-ID-ИЗ-ОТВЕТА'
& $rentgenCommand source-list --registry 'C:\RentgenState\registry.sqlite3' --project $projectId --snapshot $snapshotId --kind module --limit 20
```

Пути BSL-модулей — первый результат. Пустой список требует проверки папки
и наличия модулей в выгрузке.

Сообщение `recovery` в stderr возможно и при успешном capture: смотрите итоговый
`result` и код завершения. При прерывании сохраните `operation_id` /
`expected_head`, прочитайте квитанцию и следуйте процедуре recovery.
Не повторяйте ту же операцию вслепую.

## Какие факты уже проверены

Оба оригинальных CI PR54: по **3164 Python / 332 Node**, без ошибок, дубликатов
и пропусков. **38 protected cases входят в Python-набор**, не добавляются сверху.
Сохранены 3158 прежних Python + 6 application-frame и 324 прежних Node + 8 bridge
случаев. Это полные прочитанные отчёты Source54. Отдельный исходный CI Main54
прошёл все четыре задания и 55 шагов; полное дерево совпало с Source54.
Числа из нового Main JUnit/TAP отдельно не перечитывались. Финальный комплект
привязан к Main54 и проверен побайтно, а установка выполнена заново.

В финальном комплекте нового main сверены все 40 записей manifest и 105 файлов
установленного кода: 90 Core, 10 Diagnostics, 5 Graph. Wheel побайтно равен
ранее проверенному M49. Комплект установлен офлайн в новое окружение;
`pip check` прошёл. Официальный MCP SDK выполнил сценарий черновика: сохранение
ревизий, чтение по частям, квитанция по прежнему operation_id в новой SDK-сессии, архивирование и восстановление.
Список содержит 32 инструмента; дополнительно проверены ограничение до трёх
инструментов, отказ чужому проекту/запрещённому инструменту и ошибки аргументов.
Четыре импортированных модуля происходят из свежей установки.
Исторические native CI проверки M49 сохраняют прежнюю область.

## Файлы и границы выпуска

Core Release содержит ровно четыре файла:

- `rentgen-core-0.1.0.dev16-windows-py311.zip`;
- `manifest.json`;
- `SHA256SUMS`;
- `RELEASE_NOTES.md`.

| Финальная привязка | Значение Root |
| --- | --- |
| Source C внутри kit и цель Core tag | `cf76dd82f7b3a727640c0e47117f86f1b62aafc8` |
| ZIP: размер / SHA256 | `20474513` / `5ce8e3b3320ddd0d0a18274e207fac5b1753cba5077b02e709efaa30ac1e9f9b` |
| Wheel / sdist SHA256 | `cac3cb17fbf0758f49ef7f9957dc4e211ae83af2a5a227cc60c320e89636eb52` / `7ce94ee79704233ceb030d5c6a661aa750748cba6bf46a94697cf2247d14d4f0` |

CI ZIP сохраняется целиком. Commit release records R может быть позже C;
его сборка не подменяет принятый комплект.

Companion 0.1.17 и официальный Cline 4.1.17 установлены в отдельный профиль
Microsoft VS Code 1.139.1 с этим Core dev16. Редактор запущен проверочным
стендом: обе версии распознаны, Companion сообщил готовность для правильного
проекта; процесс завершился с кодом 0. Задание модели и сценарий 1С не запускались.
Активация не проверяет все действия пользователя в редакторе. Реальный OwnerIPC,
cold Editor, Windows ABI/ACL handoff и модельный backend не приняты.
Ежедневный сценарий с поддерживаемой моделью остаётся открытым.

Private codec опыт согласовал один искусственный BOOTSTRAP → REFUSAL transcript,
отказ неверному request_id и owned storage cleanup после fake completion.
Он не даёт native completion authority, READY или grants и не измеряет global RSS.
Типовые базы, editor live apply, full self-hosted readiness и deployment не заявлены.
