# Рождение процессов через Windows DEBUG_PROCESS

## Назначение и статус

Этот эксперимент помогает участникам проекта проверить происхождение kernel handles при рождении процесса. [Collector на C11](../../scripts/verification/root_debug_birth.c) и [его header](../../scripts/verification/root_debug_birth.h) образуют отдельный диагностический EXE для Windows x64. Он создаёт заранее проверенный Node fixture, наблюдает родителя и одного потомка и сохраняет журнал после очистки. Локальный сценарий нужен для исследования будущего handoff владельца процесса в Рентгене.

На 3 октября 2026 года ответственным исполнителем Root выполнены два случая версии v3. Их сохранённые результаты независимо рассмотрены в пределах synthetic experiment. Editor в этих случаях не запускался. Успех имеет статус `observed_only`; логическая роль каждого кандидата остаётся `null`. Core, модели, 1С, production dispatch, OwnerIPC, EditorRole и READY остаются закрыты.

Отдельная [проверка отказа через настоящий Windows pipe](owner-pipe-refusal.md) сохраняет свой контракт: один созданный клиент, один Job и отказ перед запуском обработчика. Этот collector использует другой Job с лимитом **два процесса**, чтобы наблюдать известную пару parent–child. Лимит существующего pipe не изменён.

## Как устроено наблюдение

Весь цикл создания, ожидания событий, продолжения и очистки находится в одном главном потоке EXE. Это соответствует требованию Windows выполнять ожидание и продолжение в потоке создателя debug connection. Поток живёт до окончания проверки; передача цикла фоновому Python thread или DLL callback здесь отсутствует. [WaitForDebugEventEx](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-waitfordebugeventex), [ContinueDebugEvent](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-continuedebugevent).

Перед запуском создаётся безымянный Job: active-process cap 2, лимит памяти 256 MiB на процесс, kill-on-close. Фактические ограничения и первоначальная пустота проверяются. `PROC_THREAD_ATTRIBUTE_JOB_LIST` связывает создаваемый процесс с этим Job при рождении; память значения атрибута сохраняется до удаления attribute list. [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

Используются `DEBUG_PROCESS`, `CREATE_SUSPENDED`, `DETACHED_PROCESS`, Unicode environment и extended startup information. Наследование handles выключено, BREAKAWAY отсутствует. `DEBUG_ONLY_THIS_PROCESS` отсутствует: нужны события обоих процессов. После проверки созданного процесса, состава Job и дедлайна снимается ровно один ручной suspension count. Затем debug CREATE event удерживает выполнение до продолжения. `DETACHED_PROCESS` допускает последующий `AllocConsole`, поэтому состав Job всё равно проверяется. [Process Creation Flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags).

При каждом `CREATE_PROCESS_DEBUG_EVENT` collector регистрирует кандидата и получает собственные ненаследуемые дубликаты event `hProcess` и `hThread` **до Continue**. Через эти handles сверяются kernel identity, время рождения, image и принадлежность Job. Открытие процесса по найденному PID отсутствует. PID используется как ключ журнала. Event `hFile` закрывается проверяемым вызовом; принадлежащие системе process/thread handles не закрываются вручную. [Debugging Events](https://learn.microsoft.com/en-us/windows/win32/debug/debugging-events).

## Входы и сборка

Ответственный исполнитель заранее проверяет fixture Source и измеряет SHA-256 Node, parent script и child script. Он удерживает собственные каталоги и входные файлы, проверяет конечные пути и отсутствие reparse-подмены. Сам collector закрепляет три читаемых файла без write/delete sharing; это не заменяет проверку каталогов вызывающей стороной.

Header фиксирует little-endian x64 layout: `RDBC_ARGS` **8352 байта**, `RDBC_EVENT` **40**, `RDBC_CANDIDATE` **2096**. Вход содержит magic/version/size, ненулевую generation, четыре ограниченных абсолютных UTF-16 пути, три измеренных SHA-256 и нулевые reserved fields. Raw pointers и handles во входном файле отсутствуют. Node ограничен 128 MiB, каждый script — 8192 байт; пути — 1024 UTF-16 units.

Сборка исходников выполнялась GCC с такими параметрами:

```text
gcc -std=c11 -Wall -Wextra -Werror -O2 -municode
    -o <owned-output>/root_debug_birth.exe
    scripts/verification/root_debug_birth.c -lbcrypt
```

Здесь показаны параметры сборки. Путь output и точный compiler выбирает исполнитель в собственном каталоге. EXE принимает два пути: подготовленный `input.bin` точного размера и новый `result.json`. Готового пользовательского CLI, генератора входов или установки в Core SDK этот эксперимент не предоставляет. Повторение требует собственных закреплённых входов и отдельного решения ответственного исполнителя.

## Отказ, исключения и удержание ресурсов

Разрешён ровно один first-chance startup breakpoint в initial thread каждого кандидата. Эта ограниченная политика явно заявлена для fixture. Остальные исключения приводят к отказу; `DBG_EXCEPTION_NOT_HANDLED` сохраняет обработку исключения Windows. Неизвестный event, лишний процесс, нарушенная последовательность, превышение caps или ошибка Continue также закрывают проверку.

Лимиты составляют 512 событий и 128 зарегистрированных thread lifetimes. Ожидание разбито на интервалы до 50 ms; основной дедлайн — 5000 ms, очистка — 3000 ms. Абсолютный применимый дедлайн повторно проверяется непосредственно перед Continue. Это ограничения решения и ожиданий: синхронный kernel call и планирование ОС могут пересечь срок, поэтому физическая жёсткая граница времени не заявляется.

EXIT отмечается завершённым только после успешного Continue. Затем собственный process handle должен стать signaled, exit code должен совпасть с EXIT event, а Job — фактически опустеть. Только после этих наблюдений освобождаются удерживаемые process/thread/Job handles. Если terminal state неизвестен, handles удерживаются до выхода collector, результат отвергается, `candidates` и `ledger` скрываются. Включённый `DebugSetProcessKillOnExit(TRUE)` остаётся страховкой; завершение debugger thread не выдаётся за наблюдённую очистку. [DebugSetProcessKillOnExit](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-debugsetprocesskillonexit).

JSON ограничен 196608 байтами. Output создаётся исключительно новым файлом до child effects; ошибки записи, flush или close дают ненулевой код. Частичный receipt сохраняется и требует отказа, автоматическое перезаписывание отсутствует.

## Фактически полученные результаты

В положительном случае parent fixture запустил ровно одного child и дождался его завершения. Получены **112 событий**, два разных kernel birth, по одному разрешённому startup breakpoint и проверенное продолжение каждого события. Обе пары EXIT event / signaled process показали код **0**. Job пуст, ожидающих system handles и собственных probe handles осталось **0**. Этот счётчик относится к зарегистрированным ресурсам проверки; output закрывается отдельно, чужие handles процесса не подсчитываются.

В отрицательном случае изменён только ожидаемый parent SHA. Получен отказ `PIN_FILES` до CreateProcess: ноль кандидатов и событий, процесс не создан. Очистка завершена; поле Job empty здесь неприменимо, поскольку Job ещё не создавался. Root удерживал 18 внешних slots — 12 каталогов и 6 файлов; все закрыты без ошибок.

История сохранена: первая компиляция отказала из-за столкновения имени stage с typedef, EXE отсутствовал. В v3 переименован только stage identifier с сохранением ABI и значения. Ранее исправлены два P2: свежая проверка cleanup deadline перед Continue и удержание принадлежащих collector handles при неизвестном terminal state. Исправленные сборка и два случая приняты в указанном узком объёме.

## Граница следующего шага

Предложение instrumentation для отдельной копии Editor main.js пока имеет только Source status. Найдены causal anchors до utilityProcess.fork и на том же возвращённом объекте при spawn, но Root-authenticated witness endpoint и выбор конкретного окна остаются незаполненными prerequisites. Настоящий Editor, handoff выбранного Extension Host и связь с его kernel birth этим экспериментом не проверены. Marker, PID и успешная synthetic cleanup не предоставляют роль или разрешение выполнять рабочие задачи.
