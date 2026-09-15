# Same-process Python ImagePath for the Observer service

## Scope

`rentgen_core.service_entry` содержит рабочий `StartServiceCtrlDispatcherW`,
но обычный pip console-script launcher может передать SCM в другой процесс.
Нужен строго ограниченный ImagePath, который запускает установленный Python
интерпретатор и модуль service entrypoint в том же процессе, без произвольной
командной строки.

## Contract

`ServiceInstallSpec` сохраняет существующий режим для native `.exe` с
`--service [--config <json>]` и добавляет второй режим только для файла с
именем `python.exe` или `pythonw.exe`. Для него аргументы обязаны в точности
иметь форму:

```text
-I -m rentgen_core.service_entry --service --config <canonical-json-path>
```

Валидация не принимает другие модули, flags, environment expansion, shell
syntax, account/password/token поля или дополнительные параметры. Исполнитель
по-прежнему получает список аргументов с `shell=False`, а `binary_path`
использует quoting Windows CRT. Конфигурация не читается installer-ом.

Такой режим только формирует ImagePath и не выполняет SCM. Имя интерпретатора
проверяется по basename, файловая целостность, ACL, signing и TOCTOU остаются
обязанностью deployment. `-I` исключает user site/import path; пакет должен быть
установлен в site packages выбранного интерпретатора.

## Compatibility and failure

Старые аргументы и существующие планы не меняются. Native service executable
может использовать прежний grammar. Python mode получает тот же
`ServiceInstallSpec`/SCM operation ordering, rollback и error taxonomy. `update`
меняет весь ImagePath одним `sc config`, без перезапуска. Никакая команда не
добавляется автоматически и не запускается повторно после timeout.

Документация показывает прямой interpreter ImagePath как deployment option, но
не объявляет live SCM acceptance: требуется отдельный Windows smoke с фактическим
установленным Python, SID `LocalService`, RUNNING/STOPPED, stop во время tick и
recovery behavior.

## Verification

Добавляются RED→GREEN тесты для точной допустимой формы, отказа каждого
лишнего flag/module/argument, canonical config path, quoting, старого native
режима, plan/update consistency, secret/path sanitization и отсутствия executor
в dry-run. Полный service installer/host suite, Black, Ruff, `git diff --check`
и Product CI повторяются на exact candidate.
