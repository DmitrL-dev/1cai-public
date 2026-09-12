# Bounded Git watcher

The rentgen_core.git_watcher.GitWatcher class is a synchronous orchestration
adapter for one committed Git repository. It is intended to be called by a host
scheduler; the library does not create a background thread, service, model
request, network connection or subprocess other than the existing read-only
Git probe.

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

The watcher serializes its pass with the observer worker lock. The internal
locked write path is used only by this adapter, so a concurrent source observer
cannot publish a conflicting findings state. The lock does not freeze external
Git activity for the whole callback; the second probe detects a visible HEAD
change before persistence.

This is an orchestration boundary, not an analyzer. The callback remains
responsible for checking the exact commit and producing trustworthy findings.
The current core does not ship a repository analyzer, automatic scheduler,
notifications, branch ancestry policy or Git archive sandbox. It also does not
turn caller-supplied findings into proof that BSL, an LLM or any other analyzer
actually ran; receipts continue to state analysis="caller_supplied" and
model_calls=0.

Unit coverage in tests/unit/test_git_watcher.py checks new/unchanged commits,
retry after analyzer failure, exact context binding, dirty and foreign
repositories, HEAD races and constructor bounds.
