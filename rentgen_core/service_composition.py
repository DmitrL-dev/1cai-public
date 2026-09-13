"""Explicit, bounded Git audit composition for the existing service entrypoint.

Sources/refs are read-only. Writes are confined to existing Observer evidence,
its scheduler journal/local outbox, the owner-report store and BSL scratch data.
There is no source capture, runtime export, notification sender or SCM installer.
"""

from contextlib import nullcontext
import stat

from .errors import CoreError
from .git_observer import observe_git
from .git_watcher import (
    GitWatcher,
    GitWatcherScheduler,
    NotificationOutbox,
    SchedulerJournal,
)
from .owner_report_store import OwnerReportStore
from .service_host import WindowsServiceHost


def _safe_output_leaf(path):
    """Reject static redirection/aliasing before any worker-owned writes.

    This startup check does not pin a missing file or defend later replacement;
    the existing profile ACL and filesystem-identity obligations still apply.
    """
    try:
        if path.resolve() != path:
            return False
        info = path.lstat()
    except FileNotFoundError:
        return True
    except (OSError, RuntimeError):
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and not getattr(info, "st_file_attributes", 0)
        & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


class _LeasedObserver:
    """GitWatcher view while this worker owns the real Observer lifetime lease."""

    def __init__(self, observer):
        self._observer = observer

    def __getattr__(self, name):
        return getattr(self._observer, name)

    def locked(self):
        return nullcontext()


class _ReportingWatcher:
    def __init__(self, watcher, store, authorize):
        self.watcher, self.store, self.authorize = watcher, store, authorize
        self._last_binding = self._receipt = None

    def tick(self):
        observer = self.watcher.observer
        # GitWatcher itself permits unbound findings when no snapshot exists.
        # This composition requires a verified owner report, so refuse earlier.
        observation = observe_git(self.watcher.repository)
        evidence = observer.verify_git_snapshot(observation)
        if evidence is None:
            raise CoreError(
                "SERVICE_EVIDENCE_INCOMPLETE",
                "Published Git snapshot evidence required",
            )
        event = self.watcher.tick()
        report = observer.owner_report(evidence.snapshot_id)
        quality = report["quality"]
        if (
            event["commit"] != observation.commit
            or quality.get("status") != "available"
            or quality.get("provenance") != "git_source_verified"
            or quality.get("commit") != event["commit"]
        ):
            raise CoreError(
                "SERVICE_EVIDENCE_INCOMPLETE", "Verified owner-report binding required"
            )
        binding = (event["commit"], evidence.snapshot_id)
        if self._last_binding != binding:
            self.authorize()
            self.store.initialize()
            self._receipt = self.store.save(report, authorize=self.authorize)
            self._last_binding = binding
        return event | {"owner_report_id": self._receipt["report_id"]}


class GitAuditWorker:
    """Own one profile lease and one scheduler run, with cooperative stop."""

    def __init__(self, config):
        from rentgen_diagnostics.installed import InstalledDiagnostics
        from rentgen_diagnostics.git_bsl_analyzer import (
            BslGitAnalyzer,
            PROFILE_ID,
            SCOPE_ID,
        )
        from .diagnostics import BSL_PROFILE_ID
        from .local import LocalRuntime
        from .local_identity import current_windows_principal
        from .observer import Observer
        from .service_entry import GitServiceConfig, _invalid, _local_path

        if not isinstance(config, GitServiceConfig) or config.mode != "read-only":
            raise _invalid()
        self.config = config
        self._lease = None
        self._started = False
        observer = Observer(
            LocalRuntime(config.registry),
            current_windows_principal(),
            config.project,
            config.profile,
        )

        def authorize():
            observer._validate(observer._context(write=True))

        authorize()
        ctx = observer._context(write=True)
        source = _local_path(str(ctx.source_root), directory=True)
        state = _local_path(str(ctx.state.path.parent), directory=True)
        scratch = config.diagnostics_root / "Rentgen" / "diagnostic-runs"
        # Output placement is fixed. Do not accept journal/outbox paths or let
        # diagnostic scratch overlap the repository through this composition.
        for output in (config.profile, state, scratch.resolve()):
            if output.is_relative_to(source) or source.is_relative_to(output):
                raise _invalid()
        adapter = InstalledDiagnostics(
            local_app_data=config.diagnostics_root
        ).for_profile(BSL_PROFILE_ID)
        analyzer = BslGitAnalyzer(adapter, authorize)
        watcher = GitWatcher(
            _LeasedObserver(observer),
            analyzer,
            repository=source,
            profile_id=PROFILE_ID,
            scope_id=SCOPE_ID,
        )
        self.watcher = _ReportingWatcher(
            watcher, OwnerReportStore(state / "owner-reports"), authorize
        )
        journal_path = config.profile / "git-journal.json"
        outbox_path = config.profile / "git-outbox.json"
        paths = [config.profile / "worker.lock"]
        for path in (journal_path, outbox_path):
            paths.extend(
                path.with_name(path.name + suffix) for suffix in ("", ".lock", ".tmp")
            )
        for path in paths:
            if not _safe_output_leaf(path):
                raise _invalid()
        self.journal = SchedulerJournal(journal_path)
        self.outbox = NotificationOutbox(outbox_path)
        lease = observer.locked()
        lease.__enter__()
        self._lease = lease

    def run(self, stop):
        if self._started or self._lease is None:
            raise CoreError(
                "SERVICE_HOST_ALREADY_RUN", "Git audit worker already run or closed"
            )
        self._started = True
        scheduler = GitWatcherScheduler(
            self.watcher,
            interval=self.config.interval_seconds,
            max_cycles=self.config.max_cycles,
            max_backoff=max(3600, self.config.interval_seconds),
            should_stop=stop.is_set,
            sleep=stop.wait,
            retry_codes=WindowsServiceHost.RETRY_CODES,
            journal=self.journal,
            outbox=self.outbox,
        )
        events = scheduler.run()
        if events and events[-1].get("status") == "error":
            # A bounded scheduler may return its last retryable error when its
            # budget or a stop prevents the next attempt. It is still failure.
            raise CoreError(
                events[-1]["code"], "Git audit ended with an unresolved error"
            )
        # The journal retains the total even beyond the scheduler's 1000 events.
        return self.journal.read()["cycle"]

    def close(self):
        lease, self._lease = self._lease, None
        if lease is not None:
            lease.__exit__(None, None, None)
