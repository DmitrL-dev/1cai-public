# Проверка Git под настоящим LocalService перед приёмкой Git-службы

Основание: принятый main `c715e9b65b75ae667376f331c3c0fac14be2f7f3`, CI
36359690277. Непрерывный кандидат остаётся локальным. Прежний пятислучайный
опыт выполнялся текущим пользователем с `GIT_TEST_ASSUME_DIFFERENT_OWNER`;
его результат не подтверждает работу Git под LocalService.

## Решение и цель измерения

Использовать отдельный модуль `scm_git_probe_service.py` в подготовленном
прямом Python runtime. Он вызывает существующий `NativeService` с собственным
verification-only `worker_factory`. Coordinator создаёт одну временную службу
с фиксированным ImagePath `python.exe -I -m scm_git_probe_service --service
--config <owned service.json>`. Модуль расположен отдельно от Core; 103 файла
установленного wheel остаются прежними. Публичный ServiceInstallSpec, допускающий
только штатный Core module, не расширяется ради диагностического запуска.

Альтернативы: изменение штатной фабрики Core смешало бы измерение с новой
производственной политикой; запуск Git из подменённого scanner затруднил бы
привязку к прямому процессу службы. Выбранный модуль сохраняет настоящий SCM
процесс и явно обозначает диагностический scope.

Coordinator работает только на новой disposable Windows VM CI с SCM create
access и backup/restore privileges. NativeEvidence проверяет фактические
ImagePath, SERVICE_WIN32_OWN_PROCESS, account, PID, image и token SID `S-1-5-19`.
Неизвестная или существовавшая до опыта служба не управляется. Lifecycle:
создать → RUNNING → результаты probe → STOP → STOPPED → удалить → verify absent.
STOP и finally cleanup имеют собственный ограниченный резерв времени.

## Две принадлежащие стенду репозитории

Coordinator создаёт `fixture/git-probe/source/selected` и `fixture/git-probe/source/other` без remote
и с минимальными BSL-файлами. Их исходный владелец отличается от S-1-5-19 и
сохраняется до конца измерения. LocalService получает только Read/Execute для
исходников/репозиториев и runtime, Modify только для `fixture/service_data`.
Source registry/profile/config связываются с тем же owned workspace. Перед
запуском проверяются отсутствие links/reparse/hardlinks, полный file inventory,
хеши, DACL, владельцы и точные script/runtime hashes.

Нельзя менять владельца репозитория на LocalService ради успешного Git-командного
результата. Нельзя использовать GIT_TEST_ASSUME_DIFFERENT_OWNER в нативном опыте.
Нельзя писать safe.directory в machine/user config или использовать `*`/`/*`.

## Измерения из процесса службы

1. Сохранить SID, PID, время, SHA-256 наблюдённого PATH, результат `which git`,
   абсолютный git.exe, его SHA-256 и `git --version`. Окружение целиком не писать.
2. Выполнить selected probe с тем же удалением GIT_* и отключёнными optional
   locks/prompt/lazy fetch/fsmonitor, которое использует продукт. Это реальное
   наблюдение стандартного окружения службы; заранее успешным его не считать.
3. Отдельно выполнить isolated-default selected probe с отключённым system Git
   config и пустым caller-owned global config, чтобы исключить прежние trust
   настройки. Для этого опыта фактический чужой владелец должен дать отказ Git
   из-за ownership; другой отказ фиксируется своей причиной.
4. В следующем процессе передать только `-c safe.directory=` и точный
   `-c safe.directory=<selected absolute root>`, проверить выбранный commit/root.
5. С тем же исключением selected выполнить probe other — он должен остаться
   отвергнутым; затем selected без исключения — снова отвергнутым.

У каждого дочернего процесса — ограничение времени/вывода, argv, code,
stdout/stderr digest и owned raw файлы. Ни одна команда не изменяет Git refs,
index, исходники или настройки; ни одна не использует сеть. Помимо сравнения
bytes/tree/ref, подтверждается фактический SID процесса службы, породившего
команды, и его SCM binding.

## Очистка и границы принятия

Повторно использовать проверенные функции raw ACL/owner restoration из SCM
verifier с их полными snapshots. В finally восстановить права и владельцев всех
исходных объектов, убрать временные service ACE с новых owned evidence/state
объектов. Сохранить raw before/after поля, временную
политику и проверку восстановленного privilege state. Для новых объектов
использовать проверенную политику владельца `S-1-5-32-544`, как в существующем
cleanup; для них исходного снимка владельца нет. Evidence не удалять.

Успех означает **принято диагностическое измерение**. Поля
`native_git_scm_accepted`, `continuous_git_accepted`, `production_trust_policy_selected`,
`full_product_ready` и `production_deployment` остаются false. После измерения
нужна отдельная политика всех Git invocation paths и реальный штатный
GitAuditWorker schema 3 с BSL-LS, exact-commit capture/history, STOP/recovery,
payload нового выпуска и отдельной CI/main приёмкой.

## Детерминированные проверки до CI

- Отказ для неизвестных/вне-workspace config/module/repo paths, aliases и
  неподтверждённых runtime hashes; отказ до SCM/ACL mutation без полномочий.
- Привязка whitelist дочерних команд и выбранного репозитория; запрет wildcard
  trust, отсутствия reset и переноса trust на other/следующий процесс.
- Сохранение отдельно default и isolated окружений; отсутствие тестовой
  симуляции владельца, credentials и сетевых команд.
- Ошибка/тайм-аут Git не превращаются в успешный owner probe; cleanup запускается
  при ошибке START/STOP/probe и имеет отдельный deadline.
- Реальные current-user Git контракты проверяют процессный scope. Их нельзя
  принимать за LocalService. Только отдельный CI artifact доказывает actual SID.

## Первичные источники

- [Git safe.directory](https://git-scm.com/docs/git-config#Documentation/git-config.txt-safedirectory):
  protected configuration, сброс списком с пустым значением, точные исключения.
- [Microsoft: LocalService account](https://learn.microsoft.com/en-us/windows/win32/services/localservice-account):
  собственный профиль/контекст учётной записи и её идентичность.
- [Microsoft: CreateServiceW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-createservicew):
  явная account NT AUTHORITY\LocalService и необходимый SCM create access.

Документ подготовил основной агент. Независимое ревью не заявляется.
