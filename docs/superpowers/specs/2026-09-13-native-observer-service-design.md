# Native observer service entrypoint

## Problem and boundary

Рентген уже имеет durable Observer, bounded scheduler/host и строгий адаптер
установки через Windows Service Control Manager (SCM), но у него нет процесса,
который действительно регистрирует `ServiceMain` и принимает команды SCM.
Регистрация произвольного Python console entrypoint через `sc.exe` не создаёт
службу. Этот срез добавляет проверяемую native service boundary и оставляет
установку, ACL, подпись, recovery actions и production deployment отдельными
операциями владельца.

Результат поддерживает два явных режима worker: `max_cycles=null` работает до STOP/SHUTDOWN, а целое значение задаёт конечный бюджет для smoke и controlled runs. При `--console` тот же worker запускается без SCM. Автоматический restart и изоляция ОС не обещаются.

## Architecture

`rentgen_core.service_entry` содержит четыре изолированных слоя:

1. `ServiceConfig` загружает JSON schema 1. Разрешены только
   `service_name`, `registry`, `profile`, `project`, `scanner`,
   `interval_seconds` и `max_cycles`. Пути должны быть существующими локальными
   файлами/каталогом, абсолютными; registry — обычный локальный файл, scanner — существующий `.exe`, profile — существующий каталог, без UNC, traversal,
   alternate streams, control characters или credential-like names. Неизвестные
   поля, environment expansion, imports, shell-команды и токены отклоняются.
2. `ObserverWorker` строит существующий `LocalRuntime` с
   `RentgenGraphReaderFactory` и `RentgenCapturedGoBuilder`, создаёт `Observer`
   с текущим Windows token principal и выполняет `_tick()` под его lock. Worker
   ограничен `max_cycles` (или работает до остановки при null), ждёт через interruptible `Event` и считает любую ошибку Observer fatal без автоматического retry; выполняет
   cleanup ровно один раз.
3. `NativeService` владеет lifecycle и Win32 seam. В service mode вызываются
   `StartServiceCtrlDispatcherW`, `RegisterServiceCtrlHandlerExW` и
   `SetServiceStatus`; callback для STOP/SHUTDOWN только выставляет Event.
   ServiceMain публикует `START_PENDING`, запускает worker, затем `RUNNING`, при
   остановке `STOP_PENDING` и в конце `STOPPED`. Ошибка сообщает только
   числовой Win32 exit code и общий публичный статус, не раскрывая пути,
   секреты или traceback.
4. CLI выбирает ровно один режим (`--service` или `--console`) и один config.
   Console mode печатает ограниченные JSON-события и возвращает ненулевой код
   при ошибке; service mode не пишет в stdout и не зависит от интерактивной
   консоли.

Win32 вызовы проходят через маленький injectable seam. На non-Windows service
mode завершается typed `SERVICE_PLATFORM_UNSUPPORTED`; config parsing и dry
console planning остаются тестируемыми без SCM.

Идентичность не задаётся в JSON и не может быть подменена аргументом. Служба
получает тот же Windows token, под которым SCM запустил executable. Поэтому
профиль и членство проекта должны быть заранее подготовлены для выбранной
учётной записи службы (текущий installer по умолчанию использует
`NT AUTHORITY\\LocalService`); запуск от другого аккаунта приводит к обычному
`PROJECT_FORBIDDEN`/`OBSERVER_PROFILE_MISMATCH` и не выполняет запись.

## Failure and recovery contract

- До создания runtime factory конфигурация и runtime binding проходят все проверки; в service mode dispatcher и `START_PENDING` публикуются до тяжёлого worker startup. При ошибке процесс сообщает generic `SERVICE_CONFIG_INVALID`/`SERVICE_WORKER_FAILED` без echo входного значения.
- STOP/SHUTDOWN не прерывает активный `_tick()` и не убивает дочерние процессы;
  worker завершает текущую операцию, освобождает lock и закрывает только свои
  ресурсы. Повторный stop идемпотентен.
- Fatal Observer/CoreError не ретраится автоматически и приводит к
  `STOPPED` с фиксированным generic status. Retry/backoff остаются контрактом
  существующего scheduler, если вызывающий слой его использует.
- Если cleanup завершается ошибкой, исходная ошибка сохраняется; вторичная
  ошибка доступна только локальному диагностическому журналу теста и не попадает
  в публичный SCM текст.
- SCM install/update/start/stop/uninstall по-прежнему выполняются только
  `WindowsServiceInstaller`; service entrypoint не мутирует SCM сам.

## Verification

Тесты подменяют Win32 seam и worker factory и проверяют:

- строгую schema/path/secret validation и отсутствие побочных эффектов до старта;
- последовательность status transitions и numeric exit status;
- STOP/SHUTDOWN до и во время tick, идемпотентность и cleanup после ошибок;
- bounded console cycles, retry/fatal distinction и generic output;
- отказ service mode на non-Windows и отсутствие SCM calls в console mode.

Локальные тесты не являются live SCM installation, service-account, reboot,
recovery-policy, signing или native 1C acceptance. Такие доказательства
потребуют отдельного разрешённого Windows окружения и не входят в этот commit.





