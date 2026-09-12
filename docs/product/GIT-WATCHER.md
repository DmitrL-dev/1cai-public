# Bounded Git watcher

The rentgen_core.git_watcher.GitWatcher class is a synchronous orchestration
adapter for one committed Git repository. A bounded foreground
`GitWatcherScheduler` is available for repeated calls; the library still does
not create a background thread, service, model request or network connection.

    from rentgen_core.git_watcher import GitWatcher

    watcher = GitWatcher(observer, analyze_commit)
    result = watcher.tick()

The callback receives a GitObservation containing the canonical project root,
full commit SHA and symbolic ref. It must return a complete FindingReport with
the exact same observation, profile and scope. The observer then applies the
existing provenance, finding identity, replay, lifecycle, byte and authorization
checks and stores the receipt atomically.

On the first commit the result has status="analyzed". A second call for the same
commit returns status="unchanged" without invoking the callback. A new commit is
analyzed once. If the repository is dirty, the probe fails closed. The watcher
probes HEAD again after the callback; a changed commit returns GIT_HEAD_CHANGED
and is not recorded. Analyzer exceptions are propagated and the commit remains
eligible for a later retry.

When a previous finding state exists, the watcher also requires the observed
commit to descend from the last analyzed commit using a read-only
`git merge-base --is-ancestor` probe. A force-push or unrelated history returns
`GIT_HISTORY_REWRITE` before the analyzer runs; an unavailable ancestry probe
returns `GIT_ANCESTRY_FAILED`. The caller must create a new observer/profile
baseline explicitly before analyzing a rewritten history.

The watcher serializes its pass with the observer worker lock. The internal
locked write path is used only by this adapter, so a concurrent source observer
cannot publish a conflicting findings state. The lock does not freeze external
Git activity for the whole callback; the second probe detects a visible HEAD
change before persistence.

`GitWatcherScheduler` can receive a `SchedulerJournal` pointing to an explicitly
owned JSON file. It writes a fsync-plus-rename record before and after each
cycle; a process that dies leaves `phase="running"`, and a later run refuses to
continue until an operator calls `journal.recover(reason)`. Fatal permission,
history-rewrite and journal errors are recorded and propagated. The returned
event list retains only the latest 1000 cycles, so an unbounded foreground run
does not grow memory without limit. This makes restarts observable without
pretending that the library is a Windows service; notifications and service
lifetime remain the caller's responsibility.

For delivery, pass a `NotificationOutbox` to the scheduler. Each cycle event is
stored in an atomic, bounded JSON queue with a monotonic ID. A host adapter reads
`outbox.peek(limit)` and calls `outbox.ack(id)` only after its channel accepted
the event; a corrupt queue, unknown ID or full queue fails closed. The outbox
does not open a network connection and does not retry an external delivery on
its own, so an interrupted sender leaves the event pending for explicit retry.

This is an orchestration boundary, not an analyzer. The callback remains
responsible for producing trustworthy findings. The optional BSL-LS adapter is
described in [GIT-BSL-ANALYZER.md](GIT-BSL-ANALYZER.md); other analyzer adapters,
notifications and Git archive sandbox are not included.
Caller-supplied reports continue to state analysis="caller_supplied" and
model_calls=0.

Unit coverage in tests/unit/test_git_watcher.py checks new/unchanged commits,
retry after analyzer failure, exact context binding, dirty and foreign
repositories, HEAD races, history rewrites, scheduler backoff/stop and
constructor bounds. Journal tests cover interrupted-run recovery, clean stop,
fatal event retention and corrupt timestamps; outbox tests cover enqueue/peek/
ack, corruption and scheduler emission. The BSL-LS Git adapter has separate
blob/provenance and incomplete-result tests.
