"""Bounded foreground lifetime for a caller-owned Windows service adapter.

This module does not install a service, start a thread or deliver notifications.
"""

from threading import Event, Lock

from .errors import CoreError
from .git_watcher import GitWatcherScheduler


class WindowsServiceHost:
    """Run a configured scheduler once, with cooperative stop and finite budget.

    Call ``stop`` or ``cancel`` from the caller's service control callback.
    Cancellation wakes interval/backoff waits; an active tick must return first.
    The supplied scheduler remains caller-owned and must not run concurrently.
    """

    RETRY_CODES = frozenset(
        {
            "GIT_PROBE_FAILED",
            "GIT_ANCESTRY_FAILED",
            "GIT_HEAD_CHANGED",
            "GIT_TRACKED_DIRTY",
        }
    )

    def __init__(self, scheduler, *, max_cycles=100, cleanup=None):
        if not isinstance(scheduler, GitWatcherScheduler):
            raise CoreError(
                "SERVICE_HOST_INVALID", "Configured GitWatcherScheduler required"
            )
        if type(max_cycles) is not int or not 1 <= max_cycles <= 10000:
            raise CoreError("SERVICE_HOST_INVALID", "max_cycles must be 1..10000")
        if cleanup is not None and not callable(cleanup):
            raise CoreError("SERVICE_HOST_INVALID", "Cleanup callback must be callable")
        self._stop_event = Event()
        self._run_lock = Lock()
        self._started = False
        self._cleanup = cleanup
        self._source_stop = scheduler.should_stop
        retry_codes = self.RETRY_CODES
        if scheduler.retry_codes is not None:
            retry_codes = retry_codes.intersection(scheduler.retry_codes)
        self._scheduler = GitWatcherScheduler(
            scheduler.watcher,
            interval=scheduler.interval,
            max_cycles=min(max_cycles, scheduler.max_cycles or max_cycles),
            max_backoff=scheduler.max_backoff,
            sleep=self._wait,
            should_stop=self._should_stop,
            journal=scheduler.journal,
            outbox=scheduler.outbox,
            retry_codes=retry_codes,
        )

    def stop(self):
        """Request cooperative stop; safe before run and from another thread."""
        self._stop_event.set()

    def cancel(self):
        """Request the same cooperative stop as a service cancellation callback."""
        self.stop()

    def _should_stop(self):
        return self._stop_event.is_set() or self._source_stop()

    def _wait(self, seconds):
        self._stop_event.wait(seconds)

    def run(self):
        """Run once and clean up; propagate fatal errors and never restart."""
        with self._run_lock:
            if self._started:
                raise CoreError("SERVICE_HOST_ALREADY_RUN", "Host already started")
            self._started = True
        primary_error = None
        try:
            return self._scheduler.run()
        except BaseException as error:
            primary_error = error
            raise
        finally:
            if self._cleanup is not None:
                try:
                    self._cleanup()
                except BaseException as cleanup_error:
                    if primary_error is None:
                        raise
                    primary_error.add_note(
                        f"Service host cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}"
                    )
