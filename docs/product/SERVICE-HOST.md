# Native Observer service entrypoint and bounded Git audit composition

## Git audit composition (schema 2)

`rentgen_core.service_composition.GitAuditWorker` connects the existing
`GitWatcherScheduler`, read-only `BslGitAnalyzer`, durable Observer findings,
`SchedulerJournal`, `NotificationOutbox` and owner-report builder/store through
the same `rentgen-service` console and native SCM entrypoint. It uses only built-in
components. Schema 1 source Observer configurations keep their existing behavior.

```json
{
  "schema": 2,
  "service_name": "Rentgen.GitAudit",
  "registry": "C:\\Rentgen\\registry.sqlite3",
  "profile": "C:\\Rentgen\\git-observer-profile",
  "project": "6e461c4d-e19c-4e37-85b3-3aa0961580b7",
  "diagnostics_root": "C:\\Rentgen\\diagnostics",
  "interval_seconds": 60,
  "max_cycles": 1,
  "mode": "dry-run"
}
```

Use the same `--console --config <absolute-local.json>` grammar. `mode` defaults
to `dry-run`: only strict configuration and existing local paths are validated;
no worker, Git/BSL process, journal, outbox or report is created. This is not a
runtime-readiness or authorization check. Explicit `mode: "read-only"` enables
the audit. These are the only accepted modes. `max_cycles` defaults to 1 and must
be an integer from 1 to 10000; null/unbounded runs are rejected for schema 2.
`interval_seconds` is required and bounded to 5–86400. All other shown fields
are required; unknown fields, duplicate JSON keys, identity overrides, arbitrary
commands, scanner selection and notification URLs are rejected. Schema 2 uses
the same 16 KiB JSON, public metadata and canonical local path rules as schema 1.

`diagnostics_root` is an explicitly selected existing installation base. The
fixed installed BSL profile resolves under `<diagnostics_root>\Rentgen\runtimes`
and writes bounded scratch attempts under `Rentgen\diagnostic-runs`; the existing
adapter verifies its pinned runtime before execution. No download, source
capture/publish, source edit, Git fetch/checkout, model, runtime exporter or
notification sender is attached. Read-only refers to repository sources/refs:
the enabled audit writes local evidence and BSL scratch data.

The current Windows principal must already have project access and an existing
matching Observer profile. The worker acquires that profile's lease before
RUNNING and retains it until cleanup; an internal leased view lets GitWatcher
reuse that ownership without acquiring a nested lease. Scheduler journal and
outbox paths are fixed as `git-journal.json` and `git-outbox.json` in the profile.
Their initial canonical paths must stay at those exact locations. Existing
journal/outbox leaves, their `.lock`/`.tmp` siblings and the profile `worker.lock`
must be regular single-link files without symlink/reparse redirection. This
schema 2 startup check rejects static hardlink aliases before auxiliary lock
initialization; schema 1's path contract is unchanged. Profile,
state and scratch directories cannot overlap sources. This does not add an
OS sandbox or protection against later path replacement; existing deployment
ACL and filesystem-identity obligations still apply.

Each tick requires a previously published snapshot whose supported source
digest matches clean Git, then runs the existing watcher. Complete BSL evidence
and an owner report with matching commit and `git_source_verified` provenance
are mandatory before a success event is enqueued. Missing snapshot, incomplete
analysis or unavailable quality fails closed. This worker does not update a
stale snapshot; a separately authorized publisher must do that first. Runtime
business metrics remain `not_available`. Reports are saved in the existing
project state `owner-reports` store; each success outbox event includes its
`owner_report_id`. Unchanged commit/snapshot pairs reuse a receipt within one
lifetime; a new lifetime may create a new receipt.

One scheduler owns the finite cycle budget and existing restricted transient
backoff. Its wait uses the service stop Event, so STOP/SHUTDOWN or a console
stop wakes interval/backoff waiting. An active tick finishes before cleanup;
there is no forced termination or wall-clock stop deadline. Journal, findings,
reports and outbox remain separate durable stores, not one transaction: later
failure may leave findings or a report without a success notification. Existing
bounded stores, full-queue failures and explicit interrupted-journal recovery
apply; no auto-ack, retention, restart or recovery is introduced.

If the scheduler returns with an unresolved final `error` event because the
cycle budget or stop prevented another retry, the worker raises that event's
CoreError code. The entrypoint reports `SERVICE_WORKER_FAILED` rather than a
successful stopped lifetime. A later successful cycle clears a prior transient
failure; stopping before the first tick or after success remains graceful.

`tests/unit/test_service_composition.py` checks strict/default config, actual
Git/Observer/store wiring with a typed fake BSL executor, fail-closed evidence,
output-path containment and cooperative stop; the same pipeline is exercised
through a mocked SCM lifecycle. No live SCM install/start/apply, service-account
acceptance or native BSL acceptance is implied.

## Source Observer entrypoint

`rentgen_core.service_entry` supplies a stdlib/ctypes Windows SCM boundary and
the `rentgen-service` console command. The source Observer worker uses the
existing `LocalRuntime`, `RentgenGraphReaderFactory`, `RentgenCapturedGoBuilder`
and `Observer` composition. This is an adapter contract proof with mocked SCM,
not live service deployment or production acceptance. The source worker is
separate from the bounded `GitWatcherScheduler` host described below.

Use an existing protected configuration file with this exact JSON schema:

```json
{
  "schema": 1,
  "service_name": "Rentgen.Observer",
  "registry": "C:\\Rentgen\\registry.sqlite3",
  "profile": "C:\\Rentgen\\observer-profile",
  "project": "6e461c4d-e19c-4e37-85b3-3aa0961580b7",
  "scanner": "C:\\Rentgen\\scanner.exe",
  "interval_seconds": 60,
  "max_cycles": 1
}
```

All fields except `max_cycles` are required. `max_cycles` is either an integer
from 1 to 10000, or `null`/absent to run until STOP, SHUTDOWN or failure. An
integer budget terminates the lifetime once; there is no automatic restart.
`interval_seconds` is an integer from 5 to 86400. Booleans and floating point
numbers do not satisfy either integer contract. For a bounded console smoke
test, retain `max_cycles: 1` and run:

```powershell
python -m rentgen_core.service_entry --console --config C:\Rentgen\settings.json
```

This performs an authorized Observer tick and can capture/publish local state;
it is not a dry run. The existing Observer profile must already belong to the
current Windows process principal and project. The adapter never initializes
or rebinds a profile, changes membership, selects an identity from JSON or
invokes `Observer.retry()`. `Observer.locked()` validates project permissions
and profile binding and holds the lease for the entire worker lifetime; `_tick`
is the explicit internal adapter used while that lease is held, as in the
existing Observer CLI. `close()` releases that lease. The runtime's other
resources remain scoped to its existing operations.

The registry is an existing regular local file, not a JSON configuration. The
profile is an existing directory; the scanner is an existing `.exe` file.
The configuration itself is an existing `.json` file. Every path is absolute,
at most 240 characters, and checked again after canonical resolution. UNC and
device paths, mapped remote/unknown drives on Windows, traversal, alternate
streams, reserved Windows names, control/surrogate characters, `%` expansion
and credential-like names are rejected. Canonicalization follows links;
hardlinks are accepted. These checks do not establish ACLs, executable trust,
file identity or protection against replacement between validation and use.

Config reads retain at most 16 KiB plus one overflow byte. Invalid UTF-8, BOM,
duplicate JSON fields, nonfinite numbers, unknown/missing fields and invalid
canonical project UUIDs fail closed. No configuration field loads a module,
executes a shell command, supplies an environment or carries credentials.
Names and paths are public metadata; arbitrary opaque secrets disguised as
names cannot be detected. Keep credentials out of configuration and argv.

Only `--console --config <path>` or `--service --config <path>` is accepted;
duplicate/extra arguments and abbreviations are rejected without echoing input.
Console mode emits one small JSON outcome with a completed cycle count, or a
fixed generic error code, and returns 0 or 2. It does not print Observer events
or raw exception text. Ctrl+C in console mode releases owned resources. A
trusted embedding can pass `worker_factory(config)` and a console `stop_event`
directly in Python. The returned worker must implement `tick()` and `close()`;
the factory owns cleanup if construction fails before it returns a worker.
The entrypoint calls a returned worker's cleanup once, including after failure.

## SCM lifetime and deployment boundary

Service mode checks the Windows platform before loading config or runtime, then
connects the process's main thread with `StartServiceCtrlDispatcherW`. The
own-process dispatch table's name is ignored by Windows; the actual service
name from `ServiceMain`'s first argument is registered and checked against
`config.service_name`. Extra SCM start arguments are rejected, never interpreted
as config overrides. See Microsoft's
[dispatcher contract](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-startservicectrldispatcherw).

`ServiceMain` immediately calls `RegisterServiceCtrlHandlerExW` and reports
`START_PENDING` with no accepted controls. One worker thread then loads config,
authenticates and acquires the Observer lease. A ready handshake allows
`RUNNING` only after startup succeeds. The service accepts STOP and SHUTDOWN;
`HandlerEx` only signals events and returns, without worker joins or I/O.
INTERROGATE returns success without publishing another status; unsupported
controls return `ERROR_CALL_NOT_IMPLEMENTED`. These follow Microsoft's
[control handler contract](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nc-winsvc-lphandler_function_ex).

The ServiceMain coordinator owns every status write. On a stop request or
worker completion/failure it reports `STOP_PENDING`, disables accepted controls,
allows cleanup and joins the worker, then attempts exactly one `STOPPED` report.
There are no later status writes. Stop observed before the RUNNING decision
skips RUNNING. An already in-flight RUNNING report can race with a new stop
request and is followed by STOP_PENDING; Event/WinAPI are not an atomic pair.
SCM API failures stop the worker cooperatively and make the overall result a
failure; registration failure has no handle with which to report STOPPED.

All worker exceptions are fatal in service mode. There is no retry/backoff
policy or automatic recovery in this source worker. Cleanup failure also fails
the lifetime, and a simultaneous stop cannot erase a failure. SCM receives only
fixed numeric failure statuses (`ERROR_SERVICE_SPECIFIC_ERROR` / 1066, with
service-specific 1=config, 2=worker, 3=SCM); service mode emits no console output.
Raw exceptions, tracebacks, notes and event payloads are not copied into public
outcomes. The existing Observer persistence retains its own evidence rules.

Interval waits are interruptible. An active factory, tick or cleanup must return
on its own; this adapter does not forcibly terminate a thread/process or promise
a wall-clock stop deadline. Pending statuses use a 30-second initial wait hint
and one checkpoint, with no timer pretending that a hung operation is making
progress. Shutdown can outlast Windows's deadline. Hard termination cannot
guarantee cleanup or a final SCM status; interrupted Observer jobs require the
existing explicit recovery workflow. See Microsoft's
[status reporting requirements](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-setservicestatus).

**The installed `rentgen-service.exe` console-script launcher is not proven as
an SCM service image.** A pip launcher can create a child Python process while
SCM owns the launcher process. The dispatcher must run in the actual service
process. The installer now supports a fixed direct-interpreter ImagePath using
`python.exe`/`pythonw.exe` with exactly
`-I -m rentgen_core.service_entry --service --config <path>`, alongside its native
EXE grammar. The package must be installed in that interpreter's site-packages;
`-I` excludes working-directory and user-site imports. The executable basename
does not prove interpreter integrity or same-process behavior, and this change
does not build a native launcher or perform live SCM acceptance. See
[SERVICE-INSTALLER.md](SERVICE-INSTALLER.md) for validation and deployment bounds.

The installer defaults to `NT AUTHORITY\LocalService`. That principal's project
membership and exact Observer profile binding must be provisioned separately;
a profile initialized by an interactive user is not automatically usable.
Account ACLs, signing, packaging, reboot/start/stop/recovery behavior and live
SCM acceptance remain unverified. Tests exercise config, source adapter lease
ownership, foreground budgets, mocked native ABI calls, startup/control races,
failure statuses and cleanup; no live SCM install/start was performed.

## Bounded Git scheduler host

`rentgen_core.service_host.WindowsServiceHost` adds a foreground lifetime to an
already configured `GitWatcherScheduler`. It is an integration boundary for a
caller-owned Windows service adapter. It does not register with the Windows
Service Control Manager, install a service, create a worker thread, configure
accounts or recovery actions, or provide a service executable or CLI command.

```python
from rentgen_core.git_watcher import GitWatcherScheduler
from rentgen_core.service_host import WindowsServiceHost

# watcher already contains the authorized Observer and analyzer callback.
scheduler = GitWatcherScheduler(watcher, interval=60, journal=journal)
host = WindowsServiceHost(scheduler, max_cycles=100, cleanup=close_owned_resources)
# The embedding application's stop/cancel callback calls host.stop().
events = host.run()
```

The host runs synchronously once. `max_cycles` is an integer from 1 to 10000
(default 100); a smaller scheduler limit is retained. The host never starts a
second scheduler run when this budget is exhausted. Events retain the scheduler's
existing bound of the most recent 1000 cycles. No wall-clock deadline is promised:
the caller's analyzer, journal I/O and cleanup must each finish on their own.

`stop()` and `cancel()` are equivalent idempotent, thread-safe requests. They may
be called before `run()`, during a tick or during interval/backoff waiting. A
request wakes the host's wait and prevents a later tick; an active tick is allowed
to finish with its existing observer lock and persistence rules. A stop racing
with the start of a tick may allow that tick to finish. The host neither kills
processes nor cancels an analyzer internally. The original scheduler stop
predicate is also checked between ticks, but changing that predicate does not
wake an active wait: a service control callback should call `host.stop()`.

The host copies scheduler configuration and owns the wait/stop callbacks for
that run. It leaves the supplied scheduler unchanged, preserving its watcher,
interval, backoff cap, journal and optional local outbox. Its custom `sleep`
callback is replaced by an interruptible `threading.Event.wait`. The caller must
not run the supplied scheduler or reuse its journal concurrently. A second or
concurrent `host.run()` fails with `SERVICE_HOST_ALREADY_RUN`; create a new host
only after explicitly deciding to start another bounded run.

Host retries are restricted to `GIT_PROBE_FAILED`, `GIT_ANCESTRY_FAILED`,
`GIT_HEAD_CHANGED` and `GIT_TRACKED_DIRTY`, using the scheduler's capped
exponential backoff. A successful cycle resets backoff. If the supplied scheduler
has an explicit `retry_codes` set, the host uses its intersection with this list;
an empty set allows no retries. All other `CoreError` codes, including unknown
ones, are fatal and propagate. Existing scheduler fatal codes cannot be made
retryable. Each allowed failure remains visible as an error event and consumes
one cycle. Calling `GitWatcherScheduler` directly without `retry_codes` retains
its existing error policy.

An optional `cleanup` callback runs exactly once after the accepted run, on
completion, cancellation or failure. The caller defines which resources it
owns; the host does not guess `close()` methods on the watcher or observer.
Cleanup errors propagate after a successful run. If a run has already failed,
the original exception is retained and a cleanup failure is attached as a
Python exception note. Secondary failures while recording a scheduler failure
or closing its journal are likewise attached to the primary exception; a failed
diagnostic write cannot guarantee a durable fatal event. A process termination
cannot guarantee cleanup: the
existing scheduler journal requires explicit operator recovery for a leftover
`running` record. No automatic recovery or restart is performed.

No native 1C execution or external notification delivery is introduced. Analyzers
are supplied by the caller and retain their own effects and timeout obligations.
The optional outbox remains a local queue; the host neither sends nor acknowledges
its events. With no outbox configured, the host creates no notification channel.

`tests/unit/test_service_host.py` covers finite budgets, stop before/during a tick,
waking backoff from another thread, capped/reset backoff, cleanup, fatal error
identity, explicit retry restrictions and unchanged scheduler configuration.
These are library contract tests; they do not constitute SCM installation,
service account, reboot, recovery-policy or native 1C acceptance evidence.
