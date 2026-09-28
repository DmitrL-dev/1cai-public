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
- [ ] Verify the seven affected regression suites, document the explicit setting,
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

## Task 3 — production capture and actual native qualification

- [ ] Bound production stdout during reading, preserve command-specific error
  codes, timeout and same-child reap; add overflow/timeout tests using actual
  child processes before integrating that boundary.
- [ ] Prepare an installed stock schema 3 fixture with actual foreign owners,
  native BSL runtime, real Git and raw SCM/process/ACL proofs.
- [ ] Verify exact commit capture/history, STOP/recovery, no source mutations and
  cleanup in privileged Windows CI. Keep unsuccessful raw artifacts.
- [ ] Qualify source/main/new Core release and publish detailed immutable assets
  with anonymous readback. Full product gaps remain separate; no deployment.
