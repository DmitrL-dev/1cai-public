# Bounded Windows service host lifetime

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
