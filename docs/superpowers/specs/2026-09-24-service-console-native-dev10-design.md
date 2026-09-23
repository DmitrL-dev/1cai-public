# Установленный Core dev10: отдельный консольный процесс Observer

## Цель

Подтвердить, что уже опубликованный Core `0.1.0.dev10` запускает настоящий
`rentgen_core.service_entry --console` в отдельном процессе и выполняет один
цикл Source Observer на собственном зарегистрированном проекте. Проверить
повторный запуск, сохранность источника, durable report и освобождение lease.

## Выбранный сценарий

Verifier создаёт новое принадлежащее тесту дерево на фиксированном локальном
томе: один небольшой BSL-модуль, SQLite registry, project state и Observer
profile. Текущий Windows principal регистрирует проект и инициализирует
профиль через установленный Core. Бинарный `bsl-scan.exe` и wheel сверяются с
точным публичным ZIP dev10. Python запускается с `-I`; verifier проверяет,
что `rentgen_core` загружен из установленной среды, а не из checkout.

Первый дочерний процесс с JSON config `schema: 1`, `max_cycles: 1` должен
вернуть `status: stopped`, `cycles: 1`, создать один опубликованный snapshot и
один durable report. Verifier связывает report с project/source digest и
сверяет исходный BSL-файл побайтово. Затем новый процесс с тем же config
делает один unchanged tick без новой generation/report. Lease после каждого
процесса должен освобождаться. Негативный запуск с неверным project ID
возвращает bounded ошибку, не создавая report и не меняя источник.

Полные локальные stdout/stderr, config, registry и source остаются в каталоге
запуска. Публичная квитанция содержит версию, SHA256 ZIP/wheel/scanner,
идентификаторы проекта и snapshot, хэши исходника, счётчики reports/generations,
коды процессов и статусы; абсолютные пути исключены. Скрипт не принимает
существующий путь к проекту или базе и требует новый `--output`.

## Границы

Это запуск console entrypoint, а не регистрация или запуск через Windows SCM.
Проверяется Source Observer schema 1, без GitAuditWorker schema 2/3, внешней
доставки уведомлений, HTTPS, модели, клиентской базы 1С и production deployment.
Один синтетический модуль не квалифицирует типовые конфигурации.
