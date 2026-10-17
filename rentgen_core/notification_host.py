"""Explicit foreground scheduling for a caller-owned notification outbox."""

from threading import Event, Lock

from .errors import CoreError
from .git_watcher import NotificationOutbox
from .notification_delivery import WebhookAdapter, deliver_outbox
from .notification_journal import DeliveryJournal, RetryPolicy


class _Stopped(Exception):
    """Internal cooperative stop, including the boundary before an ack."""


class NotificationDeliveryHost:
    """Run finite journaled batches; construction never sends notifications.

    The caller owns the endpoint, credentials, queue generation and current
    permission check. Every batch uses the same durable journal and retry
    policy. ``stop`` wakes idle waits; an active transport must return first.
    This host creates no thread and installs no service.
    """

    def __init__(
        self, outbox, adapter, *, authorize, journal,
        interval_seconds=30, max_cycles=1, batch_limit=100,
        retry_policy=None, clock=None,
    ):
        if (
            not isinstance(outbox, NotificationOutbox)
            or not isinstance(adapter, WebhookAdapter)
            or not isinstance(journal, DeliveryJournal)
            or not callable(authorize)
            or type(interval_seconds) is not int or not 5 <= interval_seconds <= 86400
            or type(max_cycles) is not int or not 1 <= max_cycles <= 10000
            or type(batch_limit) is not int or not 1 <= batch_limit <= outbox.MAX_EVENTS
            or (retry_policy is not None and not isinstance(retry_policy, RetryPolicy))
            or (clock is not None and not callable(clock))
        ):
            raise CoreError("NOTIFICATION_HOST_INVALID", "Invalid delivery host configuration")
        queue_paths = {outbox.path.with_name(outbox.path.name + suffix)
                       for suffix in ("", ".lock", ".tmp")}
        journal_paths = {journal.path.with_name(journal.path.name + suffix)
                         for suffix in ("", ".lock", ".tmp")}
        if journal.namespace != adapter._namespace or queue_paths & journal_paths:
            raise CoreError("NOTIFICATION_HOST_INVALID", "Invalid delivery journal binding")
        self._outbox, self._adapter, self._journal = outbox, adapter, journal
        self._authorize = authorize
        self._interval, self._max_cycles, self._limit = interval_seconds, max_cycles, batch_limit
        self._policy = RetryPolicy() if retry_policy is None else retry_policy
        self._clock = clock
        self._stop = Event()
        self._run_lock = Lock()
        self._started = False
        self._last_results = ()

    @property
    def last_results(self):
        """Receipts of the last completed batch only, bounded by batch_limit.

        A stopped/failed batch may have durable effects; inspect the journal
        before recovery. This tuple is neither an audit log nor an idle signal.
        """
        return self._last_results

    def stop(self):
        self._stop.set()

    def _wait(self, seconds):
        self._stop.wait(seconds)

    def _authorized(self):
        if self._stop.is_set():
            raise _Stopped()
        self._authorize()
        if self._stop.is_set():
            raise _Stopped()

    def run(self):
        """Return completed batch count; propagate failures without blind retry.

        Accepted results are persisted before the next authorization/stop
        boundary. If stopped before ack, another host recovers that ack from
        the same journal without resending. A host instance can run only once.
        """
        with self._run_lock:
            if self._started:
                raise CoreError("NOTIFICATION_HOST_ALREADY_RUN", "Delivery host already run")
            self._started = True
        cycles = 0
        try:
            while cycles < self._max_cycles:
                # Also authorize idle batches before reads and reconciliation.
                self._authorized()
                self._last_results = deliver_outbox(
                    self._outbox, self._adapter, self._limit,
                    authorize=self._authorized, journal=self._journal,
                    retry_policy=self._policy, clock=self._clock,
                )
                cycles += 1
                if cycles < self._max_cycles:
                    self._wait(self._interval)
        except _Stopped:
            pass
        return cycles
