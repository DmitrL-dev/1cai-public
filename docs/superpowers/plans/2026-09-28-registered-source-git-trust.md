# Registered source Git trust implementation plan

Execution: root agent, sequential, no subagents. Design:
`docs/superpowers/specs/2026-09-28-registered-source-git-trust-design.md`.
Current documentation source d96 has live CI attempts 36375016512/36375019607.
Keep those attempts; local implementation does not change their remote source.

## Task 1 — exact root command/environment boundary

- [x] Add test-first contracts for the frozen root, reset/exact argv, default argv,
  inherited Git variables with mixed casing and replacement refs.
- [x] Add `rentgen_core/_git_policy.py`; use it in the three direct launch sites
  without changing existing read-only commands or error semantics.
- [x] Add optional trust to observation/ancestry and BSL analyzer. Verify actual
  current-user Git blobs, unchanged repository/global config and refusal of a
  different root before subprocess launch.
- [x] Run new contracts and the existing observer/BSL analyzer suites; root review
  and commit this complete command/environment slice.

Task 1 local evidence: 26 new contracts were red before the API. After the
boundary implementation, three expectations incorrectly compared commit blobs
against worktree CRLF bytes; those tests now obtain the expected raw blob from
the original commit before any replacement ref. The final new/observer/analyzer
run passed 95 cases, zero failures/errors/skips. Real Git verifies exact argv,
unchanged repository bytes, ancestry and both default/explicit replacement-ref
cases. BSL adapter output remains injected; no LocalService/native BSL acceptance.
Public local record: `docs/product/evidence/registered-source-git-trust-local-20260928.json`.

## Task 2 — authorized service propagation

- [x] Add config red tests: omission=false, true/false, strict type and schema 1
  rejection. Preserve existing dry-run/null/scanner behavior.
- [x] Derive one GitRepositoryTrust after authorization and context binding in
  GitAuditWorker. Pass it to Observer, analyzer, watcher and reporting composition.
- [x] Verify the real Git command spy sees reset/exact permission on every child
  while the normal composition persists snapshot/findings/outbox/owner report.
  Test revocation/context mismatch before Git; existing history rewrite and
  retry/recovery contracts remain relevant.
- [x] Verify the seven affected regression suites, document the explicit setting,
  commit and publish exact tests/scope after the existing d96 CI is accounted for.

Task 2 narrow evidence: the initial run was 12 failed /18 passed before the
service API. The first implemented run was 24 passed /6 failed: the new tests
attempted to reacquire an already held lifetime lease, expected scheduler outbox
writes from a direct tick, and queried findings after revoking query permission.
The corrected tests run the real two-cycle scheduler and inspect findings only
after restoring query authorization. All 30 new cases pass. BSL output remains
injected and native SCM acceptance remains pending. Schema 2 now authorizes
before the reporting composition's first Git read, closing the demonstrated
revocation ordering gap. The existing d96 CI attempts are preserved.

The final two-new/seven-existing regression run passed 371 cases in 443.48s,
zero failures/errors/skips. It includes all 56 new root-policy/service cases.
Public Task2 record: `docs/product/evidence/registered-source-git-service-trust-local-20260928.json`.
The slice is locally reviewed and committed before remote publication; its own
source/native/new-version gates remain separate from the unchanged d96 CI.

Task1/2 published as dcff/e902 after both original d96 attempts completed and
were raw-qualified. The 31-path PR description and detailed announcement
https://github.com/DmitrL-dev/1cai-public/pull/41#issuecomment-5863528823
were read back anonymously together with both public local JSON records.
The same e902 push36378651630/PR36378654533 attempts continue; do not restart
them when observation times out. Native/source/main/new-version acceptance
remains pending.

## Task 3 — production capture and actual native qualification

- [x] Bound production stdout during reading, preserve command-specific error
  codes, timeout and same-child reap; add overflow/timeout tests using actual
  child processes before integrating that boundary.
- [ ] Prepare an installed stock schema 3 fixture with actual foreign owners,
  native BSL runtime, real Git and raw SCM/process/ACL proofs.
- [ ] Verify exact commit capture/history, STOP/recovery, no source mutations and
  cleanup in privileged Windows CI. Keep unsuccessful raw artifacts.
- [ ] Qualify source/main/new Core release and publish detailed immutable assets
  with anonymous readback. Full product gaps remain separate; no deployment.

Task3 capture slice: 20 contracts were red before the API. The first helper run
passed 20 cases, including ten actual current-user Windows Python children and
ten prelaunch/no-child cases. Integration passed 156 cases. Root inspection
then found a possible lost final write between an empty peek and exit poll.
The explicit injected race was red (1 failed /20 passed), and polling exit before
peeking made all 21 helper cases green. This is one injected race case, not an
additional native child proof. The final nine relevant suites passed 290 cases
in 318.51s, zero failures/errors/skips, including 32 new capture/mapping/real-Git
overflow cases and all 56 preceding trust/service cases. The unchanged entry
configuration and long durable-journal suites were already included in Task2's
371-pass run and were not repeated for this capture-only change.

The reader retains at most the command bound plus one byte, creates no reader
thread, kills/waits on the same child and closes stdout on overflow/timeout.
Actual oversized committed blob and a reduced-bound real listing fail before
BSL without repository mutation. Error mappings and history rewrite semantics
remain. Public local record:
`docs/product/evidence/registered-source-git-capture-local-20260928.json`.
The local capture commit is deliberately kept separate from the still-running
e902 remote source CI; its own push/source/native/new Core acceptance is pending.


Stock SCM preparation prerequisite: the original SourceObserver fixture remains
exactly five source entries by default. An explicit coordinator-supplied manifest
now allows Git metadata inside that same registered source root and compares the
complete inventory, directory flags, file sizes and SHA256 values. Names cannot
escape the fixed BSL layout or `.git`; Git root/HEAD/config/index are mandatory.
The source module stays bound to the original fixture digest. This is a verifier
argument; service JSON cannot select a manifest or relax registered-root policy.

TDD: all 27 new source-manifest contracts were red before the helper, then all
27 passed, including one real current-user Windows Git fixture and metadata hash
refusal. The final new/existing SCM verifier run was 69 passed /1 skipped;
the single existing native DACL test requires backup/restore privileges and is
exercised separately by elevated CI. This local run performs no SCM create/start,
no LocalService BSL execution, and grants no native or full-product acceptance.
Public record: `docs/product/evidence/stock-scm-source-manifest-local-20260928.json`.
The e902 original CI attempts remain unchanged; stock native composition is still
pending and the later capture/manifest source needs its own CI qualification.


Stock control/ACL prerequisites: the verification-only adapter retains the public
ServiceInstallSpec for `python.exe -I -m rentgen_core.service_entry --service`
with one fixed owned schema3 config. It hashes interpreter/config/source-manifest/
installed stock entry, retains bounded raw System32 sc.exe controls and reuses
the diagnostic adapter's acknowledged-create, authority, exact-binding and
unknown-outcome refusal guards. No diagnostic module is the new SCM ImagePath.
The coordinator must still bind verifier source hashes and installed wheel bytes.

Temporary ACL preparation now has a separate stock policy for exactly the fixed
data and diagnostics scratch trees. Original Git source, JDK/JAR, runtime and
all other fixture entries stay read/execute. Exact protected ACE validation is
applied to both partitions; the original SourceObserver ACL verifier is unchanged.
Native owner/DACL restoration and descendant cleanup remain mandatory gates.

TDD: 21 new control contracts and 14 new ACL contracts were red before their
APIs. Final four-suite regression: 138 passed /1 existing privileged DACL skip.
Control observations are injected; ACL tests construct/validate descriptors and
perform no native grants. This proves local prerequisites, not stock SCM/BSL
acceptance. Public record: `docs/product/evidence/stock-scm-control-acl-local-20260928.json`.
Pinned upstream metadata was inspected: BSL exec JAR bytes131962428; JDK ZIP
bytes205073461 with the checked-in archive hash. Java profile size343823876 is
the sum of all 490 installed manifest file sizes, not ZIP length. Preparation
will reuse the checked-in local-file installer and avoid a Java warm-up run.


Stock fixture preparation/inspection is implemented locally, not yet published.
It reuses the checked-in pinned local-file BSL installer with no downloads or
Java warm-up, initializes Git on the existing registered root using empty global
setup config/core.autocrlf=false, and writes one fixed stock schema3 config and
complete source manifest. Inspection binds verifier scripts/input hashes/actual
Git HEAD, full installed runtime pins, foreign source owner and the original
profile. Both APIs perform no SCM creation or native ACL grants.

Local TDD: nine preparation contracts were red, then green. Root review found
that false fixture commit metadata and hardlinked evidence could still pass;
two added negative cases were red (2 failed/9 passed). Inspection now uses actual
production registered-root Git observation and regular single-link metadata
validation. Final fixture/control/ACL/source-manifest run:73 passed, no skips.
Runtime installation/preflight/native owner observations in these unit cases
are injected; Git commits/observation and Windows source inventory are real.
Physical 490-file installation and LocalService/native BSL are still unaccepted.
Public local record: `docs/product/evidence/stock-scm-fixture-local-20260928.json`.

Published c1b capture/manifest/control/ACL/e902-CI record and detailed announcement:
https://github.com/DmitrL-dev/1cai-public/pull/41#issuecomment-5864184011
45 exact source paths, anonymous body/comment/four-record readback confirmed.
Keep original c1b push36383076884/PR36383080465 attempts while local stock work
continues; qualify their raw artifacts before advancing the remote branch.


Full stock native coordinator implemented locally. It launches the installed
public schema3 service directly and retains all five required gate groups:
fresh first analysis, an operator commit only while STOPPED, unchanged STOP,
actual quiet-lifetime interruption/refused restart/explicit recovery, and
history plus permission refusal before capture. Native acceptance is pending.
The new native-stock-git CI job validates exact upstream archive/JAR bytes before
extraction, reuses the 490-file installer, performs no Java warm-up, and always
retains failed controls/process observations/state/journal/outbox/owner evidence.

Private BSL scratch remains private to its real process. The coordinator does
not weaken that DACL or copy an ephemeral BSL report. Its execution provenance
gate is actual pinned Java image/token/parent/exact argv plus unchanged stock
wheel bytes, committed Git evidence and complete durable findings/owner receipts.
The interruption case is a quiet continuous wait, not an active BSL interruption.
Per-lifetime source inventories and owners are retained both before and after.

Local evidence: 30 measurement API red cases, 17 lifecycle API red cases, four
runner/job API red cases. Review reproduced a null-event running journal race;
the wait now accepts that valid intermediate state. Real stock composition with
Git/SQLite/Go and injected BSL verified two commits and an unchanged restart;
its first run exposed Windows path case normalization and is now green.
Ten-suite regression:234 passed/1 existing privileged DACL skip. Final four
coordinator suites:56 passed/0 skipped. Union:236 passed/1 skip across237 unique
cases, including60 new coordinator/optimized-interpreter cases.

Original c1b push36383076884/PR36383080465 attempts both failed after2785 passes
and one stock manifest test commit failure; native jobs were skipped. Raw JUnit,
artifact hashes and actual checkout/tree/PR parents were inspected and retained.
The unseeded author identity was reproduced with isolated empty global config;
fixed test supplies author/signing settings only for its commit. All27 manifest
cases pass. Original failed attempts remain unchanged; no c1b source success claim.
Public records: stock-scm-native-coordinator-local-20260928.json and
registered-source-git-capture-ci-failure-20260928.json under docs/product/evidence.
Root-only review; source/main/new Core qualification and full product gates open.


Root review reproduced a stale-status refusal-verifier bug after publication of
5b38b60: a new access-denied SCM start could reuse the preceding lifetime's
1066/2 STOPPED status. Require exactly one fresh fixed-service start command,
bounded and reaped capture, acknowledged zero or service-specific1066 return,
and raw stream hashes before accepting terminal status. Unknown outcomes,
timeout, overflow, another image/service/verb and boolean exit codes fail.
TDD: one lifecycle and11 control cases failed before the fix; all68 cases in
the four coordinator suites now pass without skips. This is local verifier
evidence, not actual native refusal acceptance. Original5b push36389146238 and
PR36389149702 attempts stay intact; this successor is held locally until their
terminal artifacts are collected. No push, new release or deployment here.


Root review reproduced a stock owned-child wait defect: the coordinator uses
the same copied interpreter as the SCM service, so matching its image alone
also included its own still-live PID. A clean STOP/cleanup could not complete
that wait. Exclude exactly the live verifier os.getpid; other owned service,
Java and scanner rows remain. One actual-current-PID injected regression was
red, then all69 four-suite cases passed with zero skips. Original5b attempts
remain intact; local successor and native cleanup acceptance are separate.


Original5b push36389146238 and PR36389149702 attempt1 are terminal failures.
Raw audit verified2857 Python/69 Node/two Go packages,105 byte-exact wheel files,
actual checkout/tree/PR parents, five SourceObserver LS lifetimes and one Git
ownership diagnostic LS lifetime with original ACL restoration/process binding.
The stock service acknowledged its first start, then stopped1066/2 before RUNNING.
No Java/BSL acceptance. Each200 CIM observations retained the live coordinator;
cleanup left the test service and retention incomplete. First factory/interface
exception still unidentified. Public stock-scm-full-native-ci-failure-20260928.json
accounts original attempts; no whole-source/main/release/production qualification.

Owner-view regression reproduced service-principal profile mismatch. Verifier now
authorizes its actual fixture owner with admin/analysis rights while validating
original LS profile binding. Real Git/SQLite/Go publication test now uses an
LS-bound metadata row and granted service identity; BSL/identity injected.
Revoking LS preserves owner reads; revoking owner rights refuses them. Stored
profile binding stays LS. Production Observer binding validation is unchanged.

Bounded service failure event records fixed stage/type/known reason, service name,
PID;512 characters, fixed source/Event ID1. No exception text/path/unknown code.
Logging failure cannot change result or skip cleanup; handle close in finally.
Stock failure collector retains bounded raw reads and requires observed SCM PID.
Failure remains failure; no retry, first-cycle shortcut or Java warmup.
TDD: owner1 red; event7 red/one behavior pass; reader12 red. Final service suites164
passed and four stock suites82 passed; union244 distinct cases/zero skips.
stock-scm-owner-startup-diagnostics-local-20260928.json binds source/report hashes.
Actual LS event/source CI pending. Root-only review. Modified Core payload still
requires its own later version/release after qualification.


## f885: установленная точка входа Python и диагностированный отказ

Оригинальные push 36397696372 и PR 36397703021 attempt 1 завершились failure.
Оба сохранили 2891 Python/69 Node/2 Go packages без пропусков, 105 исходных файлов
wheel, пять native SourceObserver lifetimes и отдельную Git diagnostic lifetime.
Stock остановился до RUNNING. Оба события Application/Rentgen.Core.Service/EventID1
связаны с наблюдавшимся SCM PID: factory/CoreError/SERVICE_CONFIG_INVALID.
В обоих stock cleanup ошибок нет, служба отсутствует, DACL/owners/privileges
восстановлены, шесть исходных JSON/SQLite файлов сохранены и проверены.

Причина воспроизведена через runpy с __main__: класс GitServiceConfig в точке
входа отличается от импортированного фабрикой класса. Теперь -m вызывает main
из канонического rentgen_core.service_entry. Строгая проверка фабрики сохранена.
Два первоначальных теста падали. После исправления четыре маршрута schema2/schema3,
console/injected SCM проходят с настоящей фабрикой, публикацией и освобождением
lease. Локальное объединение: 168 уникальных passed; промежуточные два отказа
из-за неверного требования к пустому stderr сохранены и исправлены.

Новый source CI ожидает 2895 Python cases/650 локальных identities. Все пять
stock групп, холодный запуск Java, реальные PID/token/parent/argv и cleanup
остаются обязательными. Actual stock RUNNING/Java ещё не квалифицированы.
Ревью выполняет root; subagents/independent review/production deployment отсутствуют.
Записи: stock-scm-module-entry-ci-failure-20260928.json и stock-scm-module-entry-local-20260928.json.


## Совместимость следующего Core dev16 / Companion 0.1.16

Оба компонента готовятся с новыми версиями. Явные списки допуска в трёх
Python-адаптерах и семи файлах Companion расширены dev16; прежние версии
и точное совпадение профиля с установленным Core/MCP сохраняются.
CI и четыре инструмента подготовки/проверки используют имена dev16.
До исправления: три отказа Python и 21 отказ Companion. После: 41 Python
и 71 Node passed без пропусков. Три новых Python-теста после форматирования
повторно passed и входят в те же 41 случая. Сборщик обнаружил 2900 Python
cases; это collection, полный прогон ещё не принят. Две локальные VSIX
сборки совпадают по байтам, версия и все 39 членов проверены.
Запись: core-dev16-compatibility-local-20260928.json. Review root only.
Нужны квалификация исходников/main, все пять native stock групп, установленный
Core, новые неизменяемые теги/артефакты и подробные публичные release notes.
Core dev15/Companion 0.1.15 сохраняются; новый выпуск и production deployment
этими локальными проверками не подтверждаются.


## 62ef: неполные WMI сведения и область Debug

Оригинальные push 36404042951 и PR 36404049696 attempt 1 завершились failure.
Оба raw-аудита подтвердили 2895 Python/69 Node/2 Go packages без пропусков,
105 исходных файлов wheel, пять SourceObserver и отдельную Git diagnostic
LocalService lifetime. Stock впервые достиг RUNNING под S-1-5-19 и завершился
чистым STOP; удержанный исходный объект процесса reap выполнен. Строгий verifier
отказал: у двух потомков NULL ExecutablePath/CommandLine. Их образы неизвестны;
durable analyzed baseline с complete findings/owner receipt не заменяет native
Java proof. Cleanup без ошибок, служба удалена, owners/DACL/privileges
восстановлены; девять JSON/SQLite файлов сохранены и проверены в каждом run.

Debug у координатора уже включён в исходных capture metadata. Исправление
явно задаёт ImpersonationLevel=3 и SeDebugPrivilege на локальном SWbemServices.
Доступность имеющейся Debug добавлена в read-only readiness. Native reads
временно используют эту привилегию с восстановлением точных исходных attributes
и закрытием token handles. Независимый reviewer нашёл чтение токена службы вне
scope в start; super().start и HeldProcess теперь находятся в одном scope.
Восемь тестов воспроизвели пропуск и затем passed, включая оба исходных состояния
Debug, ошибки base/held reads и несовпадение восстановленного состояния.

Финальные 130 scoped coordinator tests и четыре backup regressions дают 134
уникальных passed без пропусков. Добавлено 29 WMI/start/authority cases;
с пятью dev16 cases ожидаются 2929 Python tests и 684 локальные CI identities.
2929 collection не означает полный прогон. Future raw auditor требует exact
source-bound WMI command, исходные streams/rows/parent/argv, восстановление
Debug после каждого query и пяти положительных стартов. Его 92 уникальных
parser cases прошли; constructed evidence не является native выполнением.

Все пять stock групп и холодный Java запуск остаются обязательными. Эффективность
WMI исправления должны доказать новые точные source/main CI artifacts.
Пользователь разрешил двух GPT-6 Sol Max reviewers; исторические root-only
записи сохраняют свой исходный scope. Новые release/production claims отсутствуют.
Записи: stock-scm-wmi-ci-failure-20260928.json и stock-scm-wmi-debug-local-20260928.json.


### Два независимых Max ревью завершены

WMI reviewer независимо выполнил 52 injected/parser checks без пропусков;
пять итоговых source SHA совпали. Start scope, COM/raw query compatibility и
query_source delegate wiring отмечены resolved. Native acceptance не заявлен.
Dev16 reviewer сверил 30 committed paths, 105 Git/wheel/installed source/data
files, повторные Core artifacts, 30 dependency wheels, 39 VSIX members и
свежие offline Core/MCP origins/32+3 handlers. Открытых регрессий нет.
Проверка exact installed/profile версии подтверждена для run_repair.py;
general CJS client не делает отдельный version probe для каждой CLI операции.
Это прежняя граница, не новое обещание. JDK manifest/pins проверены по bytes,
физическое установленное дерево JDK reviewer не проверял. VSIX reviewer
проверил один сохранённый пакет, повторяемость VSIX — историческое root evidence.
Публичная запись: core-dev16-stock-wmi-independent-review-20260928.json.
