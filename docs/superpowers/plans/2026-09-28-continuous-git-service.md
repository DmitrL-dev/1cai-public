# Continuous Git Service Implementation Plan

> **Execution:** Основной агент выполняет план последовательно с `executing-plans`.
> Пользователь запретил субагентов. Отдельное независимое ревью не заявляется.

**Goal:** Add explicit continuous Git-service lifetime with durable counters beyond 10000.
**Architecture:** Keep existing scheduler, lease, stop and failure handling. Accept explicit null
at the service boundary and use a second journal schema for larger counters.
**Tech Stack:** Python 3.11, pytest, existing SQLite/Git/Go scanner contracts.

## Global Constraints

- Specification: `docs/superpowers/specs/2026-09-28-continuous-git-service-design.md`.
- Omitted max_cycles remains 1; integer values remain 1..10000; dry-run remains default.
- No source writes, new dependency, automatic recovery, queue truncation or production deployment.
- Schema 1 counters remain 0..10000; schema 2 counters are 0..9007199254740991.
- Preserve file line endings. Root review only. Preserve published component assets.

## Task 1: Continuous service and durable lifetime

**Files:**
- Modify `rentgen_core/service_entry.py`: GitServiceConfig and _git_config only.
- Modify `rentgen_core/git_watcher.py`: SchedulerJournal validation/serialization only.
- Modify `tests/unit/test_service_composition.py`: configuration and existing stop contracts.
- Create `tests/unit/test_continuous_git_journal.py`: journal boundary and lifetime tests.
- Modify `docs/product/SERVICE-HOST.md`: explicit null, limits and journal compatibility.

**Interfaces:** `load_config(path)` returns `GitServiceConfig.max_cycles: int | None`.
`SchedulerJournal` retains begin/read/mark_running/record/stop/recover signatures.

- [x] Inspect actual code and confirm clean baseline configuration tests on source main.
- [x] Add failing tests for explicit null in schema 2/3, existing bounded stop plus null,
  and default dry-run remaining inert. Remove None from rejected settings; retain all
  other rejected values. Parameterize the current active-tick stop test over 100/None.
- [x] Add journal tests: 10000 stays schema 1; 10001 uses schema 2; reopen/recover/new
  begin preserve state and reset only at explicit begin; invalid counters for each writer
  leave bytes unchanged; corrupted schema/counter input fails on read; 10002 real journal
  ticks stop cooperatively and retain exactly 1000 events with unchanged outbox empty.
- [x] Run these cases before implementation; retain the actual failing JUnit.
- [x] Change the service annotation to `max_cycles: int | None = 1` and replace the Git
  budget check with `cycles is not None and (type(cycles) is not int or not 1 <= cycles <= 10000)`.
- [x] In SchedulerJournal introduce `MAX_COUNTER = 2**53 - 1`. Validate int counters in
  `_document` before any file write; use schema 1 when max(cycle, failures)<=10000 else 2.
  `_read` must require an integer schema in {1,2} and apply its corresponding counter cap.
  `mark_running` must accept the same safe counter range; all existing state checks remain.
- [x] Run the failing cases again, then the five relevant suites with a fresh JUnit.
- [x] Update product documentation and retain exact red/green counts and changed hashes.
- [ ] Root review diff, `git diff --check`, commit the implementation and prepare its source PR.

## Task 2: Qualification and delivery

- [ ] Integrate the qualified SCM main without changing the dev15 candidate payload.
- [ ] Push the source branch and create/attach a draft PR with actual tests, scope and limits.
- [ ] Qualify actual source CI artifacts and merged-main CI before claiming acceptance.
- [ ] Carry changed package files into a new component version after dev15, execute its
  installation/native Git-SCM checks, publish immutable assets and detailed release notes.

## Verification commands

Use the prepared Python 3.11 test environment from the isolated workspace:

```text
python -m pytest tests/unit/test_service_composition.py -k "git_config or autonomous_config or stop" -q
python -m pytest tests/unit/test_continuous_git_journal.py -q
python -m pytest tests/unit/test_continuous_git_journal.py tests/unit/test_service_composition.py tests/unit/test_service_entry.py tests/unit/test_git_watcher.py tests/unit/test_service_host.py -q
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

Expected final result: no failures, errors or skips in these local contracts. SCM and
native BSL acceptance require their separate privileged installed-runtime run.
