# SCM Capture Observation Implementation Plan

> **For agentic workers:** Use inline execution with independent Source review. Root alone edits and runs verifiers; reviewers read bounded Source and write their own reports.

**Goal:** Retain a bounded explanation of capture-wait refusals without weakening native acceptance.

**Architecture:** Keep a pure classifier and bounded observation recorder inside the existing worker. Defer one pending success summary until the post-control phase gate; retain original exceptions and control gates.

**Tech Stack:** Python 3.11, standard library, pytest with fake clock and mocked I/O boundaries.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-02-scm-capture-observation-design.md`.
- 90 seconds, 0.05-second polling, 16 samples, 2048 bytes per sample, 40 KiB per summary.
- No local native execution, foreign process control, new dependency or helper script.
- Existing identity, active-stop, crash, corpus, budgets and cleanup gates remain mandatory.

### Task 1: Capture-wait diagnostic contract

**Files:**
- Modify: `scripts/verification/scm_acceptance_worker.py`.
- Create: `tests/unit/test_scm_capture_observation.py`.

**Interfaces:**
- `classify_capture_wait(status: dict, row: dict, previous_ids: set) -> tuple[str, dict | None]`.
- `CaptureObservation(previous_ids)`; `observe(status, row, elapsed, poll_count)`; `result(reason, error=None)`.
- `Acceptance.capture_job(previous_ids)` still returns the actual newly observed capture job or raises.

- [ ] Write tests first. Assert `(reason, job)` for old done + new capture; assert refusal for new done/report, Observer error, new job error/failed/superseded and multiple new jobs. Construct `Acceptance` with `__new__`, fake status/current/event and fake monotonic/sleep; prove timeout at 90 seconds and original exceptions survive event-write failure.
- [ ] Run `C:\Python311\python.exe -m pytest -q --tb=short tests/unit/test_scm_capture_observation.py` with plugin autoload and bytecode disabled. Expected RED because classifier/recorder do not exist.
- [ ] Add the classifier/recorder and wrap the existing `wait_until(inspect, 90, 'active capture journal')`. On failure place all formatting and emission inside a `BaseException` guard, then use bare `raise`. On success retain one pending trace and return the unchanged job immediately. Flush after the unchanged post-STOP/durable interruption phase gate; best-effort flush intervening failure before cleanup. Refuse a new capture wait while an earlier trace is pending.
- [ ] Run the same narrow verifier; require all controls PASS, including large Unicode fields, repeated transitions, last valid snapshot after read failure and the existing post-STOP gate.
- [ ] Read the actual diff and have an independent reviewer check the whole candidate. Preserve the original CI failure, commit on the existing branch, push the corrected head and announce exact scope/limits in PR #49. Qualify the new original CI attempts before merging.
