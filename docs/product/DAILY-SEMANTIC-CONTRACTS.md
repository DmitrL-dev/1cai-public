# Проверка ежедневного сценария: контракты и сохранённые результаты

Подготовлена проверка одного нового редакторского профиля: одна команда исправления, выбранная неизменяемая AI revision 2, один явно запрошенный запуск тестов и повторное чтение сохранённого результата. Восстановление использует cached commands и начинает ноль новых model/test requests.

## Что принято в этом изменении

Локально прошли 159 уникальных Node contracts без пропусков: 71 существующий Companion case, 52 semantic cases и 36 actual-host VM cases. Python проверка входов и запуска host прошла 23 уникальных cases без пропусков. Полный Python набор в этом рабочем checkout собран как 2963 cases; это collection, а не исполнение всего набора. Этот checkout основан на source6fe; включение исправления process inventory из source6bee увеличит полный Python набор на 28 cases.

Независимые ревью GPT-6 Sol / Max закрыли найденные ошибки чтения каталогов, пересечения output с входами, отсутствующих raw files и подмены сохранённой квитанции. Исходные red XML, старые source bytes и первоначальные findings сохранены. Публичная JSON запись перечисляет точные source hashes и границы проверки.

## Выбор результата и функциональная проверка

Semantic contract использует фактически загруженные validators Companion. Выбранная квитанция сравнивается целиком: project, draft, operation, revision, proposal content ID и source reference. История просматривается с ограничениями; неоднозначная или чужая запись не становится выбранным результатом. Типы UUID/hash проверяются до их использования.

Отрицательный baseline control должен содержать ровно один ожидаемый assertion failure и ноль errors/skips. Candidate оценивается отдельно по тому же профилю и case tuple. Ошибка контракта или отсутствие доказательств дают `unproven`. Проверка узнаваемого безопасного изменения ограничена конкретной трансформацией; она не принимает произвольное совпадение текста за правильный результат модели. Producer model metadata имеет отдельную границу доверия.

## Замороженные входы

`daily_frozen_inputs.py` проверяет manifest, отдельные files, ограниченные directory inventories и повторное чтение входов. Ошибки открытия или обхода каталога прекращают проверку. Output канонизируется и должен быть отдельно от manifest, файлов и всех защищённых корней; равенство, потомок и предок отклоняются до mkdir/copy/process launch.

`prepare_daily_platform.py` создаёт новую копию fixture и новый registry/profile только после этих проверок. `run_daily_semantic_editor_host.py` выбирает attempt либо recovery, использует отдельный editor profile и сохраняет input-preservation record даже при отказе выполнения. Existing profiles и старые model results не превращаются в новые подтверждённые испытания.

## Какие raw files обязательны

| Состояние | Обязательные сохранённые данные |
| --- | --- |
| Durable repair ID | request, source-ref, instruction |
| Repair с квитанцией | journal; при analysis_clean/diagnostics_present также repair report |
| saved_unverified / unresolved | Доступные raw сохраняются; отсутствующий ещё не созданный report допустим |
| Durable Companion test ID | Companion request и proposal |
| Core completed / failed либо непустой request | Core request |
| Core completed / failed | Соответственно report либо failure record |
| Phase passed / failed | JUnit, exit и отдельные phase settings |
| Phase not_run из-за compiler diagnostics | Native phase files не требуются; выполненные compile steps сохраняются |
| Объявленный выполненный step | log, stdout и stderr |
| interrupted intent до Core startup, request=null | Companion intent сохраняется; ещё не созданные Core native files не требуются |

Отсутствие обязательного файла фиксируется вместе с остальными доступными raw и снимает preservation/eligibility/recovered claims. Изменение raw между чтениями также снимает подтверждение. Для repair-only recovery выбранная квитанция должна целиком совпадать с cached repair receipt до обращения к history.

## Граница приёмки

VM/API/FS reports в этих тестах сконструированы; они подтверждают логику контракта и отказов. Фактический редактор, SDK, модель и новая native 1С конфигурация этим срезом не запускались. `pipeline_verified`, `task_accepted`, `full_product_ready` и production deployment остаются false. Приёмка реального ежедневного сценария требует отдельно сохранённых native JUnit/exit/settings/logs, module roundtrip bytes, профиля и исходного результата выбранной AI revision.

Workflow включает новые host contracts в общий Node command. Публичные release packages и предыдущие принятые результаты этот локальный срез пока не обновляет.
