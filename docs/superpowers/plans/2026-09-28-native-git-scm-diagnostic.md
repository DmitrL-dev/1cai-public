# Native LocalService Git Diagnostic Implementation Plan

> **Execution:** Основной агент выполняет `executing-plans` последовательно.
> Пользователь запретил субагентов; независимое ревью не заявляется.

**Goal:** Measure Git availability and foreign-owner refusal in one actual
LocalService process, including a selected-root exception confined to each child.

**Architecture:** Keep the public Core installer strict. Install a separately
hashed verification module into an owned direct Python runtime. A bounded
diagnostic coordinator reuses the existing fixture, native evidence and ACL
cleanup; it installs only its fixed diagnostic ImagePath.

**Tech Stack:** Python 3.11, pytest, Git, Windows SCM, accepted offline Core kit.

## Global Constraints

- Specification: `docs/superpowers/specs/2026-09-28-native-git-scm-diagnostic-design.md`.
- Actual SCM runs only on disposable privileged Windows CI. No local elevation.
- No `GIT_TEST_ASSUME_DIFFERENT_OWNER`, credentials, network, global trust or wildcard.
- LocalService SID is `S-1-5-19`; source repository owner must differ from it.
- Trust argv starts with `-c safe.directory=` and allows only the exact selected root.
- Source/runtime RX; Modify only inside the original fixture's service data.
- Original owners/DACLs restored; new objects assigned `S-1-5-32-544` during cleanup.
- Diagnostic acceptance does not accept the stock GitAuditWorker/BSL or select a
  production trust policy. Existing component tags and public assets stay immutable.
- Runtime changes in the continuous candidate require a subsequent Core version.

## Task 1: Bounded Git measurement primitives

**Files:**
- Create `scripts/verification/scm_git_probe_service.py`.
- Create `tests/unit/test_scm_git_probe.py`.

**Interfaces:**
- `probe_environment(inherited, *, isolated_global=None) -> dict[str, str]` strips
  caller Git overrides and controls locks, prompts, lazy fetch and isolated config.
- `probe_command(git, repository, *, trusted_root=None) -> tuple[str, ...]` constructs
  one fixed read-only HEAD/root probe; trust must name that call's selected fixture.
- `capture(command, environment, output, label, *, timeout=10, output_limit=32768)
  -> dict` retains bounded raw stdout/stderr and distinguishes timeout/overflow.
- `classify_probe(result, repository, commit) -> str` returns `accepted`,
  `foreign_owner_refused`, or an explicit unsuccessful reason; a generic error never
  proves an ownership denial.

- [x] Write failing tests for inherited Git config/simulation removal, default
  environment separation, exact argv/reset, wildcard and unsafe input rejection,
  output/timeout bounds and generic errors remaining distinct from owner refusal.
- [x] Run `python -m pytest tests/unit/test_scm_git_probe.py -q` and retain red JUnit.
- [x] Implement the fixed command/environment boundary. Command form:
  ```python
  (git, '--no-pager', '-c', 'core.fsmonitor=false',
   '-c', 'safe.directory=', '-c', 'safe.directory=' + selected,
   '-C', repository, 'rev-parse', '--show-toplevel', 'HEAD^{commit}')
  ```
  Omit both safe.directory pairs for the default probe. Isolated environment uses
  an empty owned `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM=1`.
- [x] Capture pipes with separate bounded readers; overflow terminates the child,
  timeout terminates and waits for that same child. Preserve the bounded bytes in
  exclusive owned files and SHA-256 them before reporting.
- [x] Check exact root plus known commit for success. Require nonzero Git exit and
  the explicit `detected dubious ownership in repository` diagnostic for refusal;
  do not classify timeout, output limit or command-not-found as owner evidence.
- [x] Run the narrow suite, inspect diff/whitespace, commit this complete slice.

## Task 2: Service worker and fixed inputs

**Files:**
- Modify `scripts/verification/scm_git_probe_service.py`.
- Extend `tests/unit/test_scm_git_probe.py`.

**Interfaces:**
- `ProbeWorker(config, config_path)` implements `tick()`/`close()` for schema1.
- Fixed input sidecar is `fixture/git-probe/inputs.json`; source roots are
  `fixture/git-probe/source/{selected,other}`; output is
  `fixture/localservice/data/git-probe`.
- `main(argv=None)` accepts only `--service --config <owned service.json>` and calls
  `NativeService(config_path, worker_factory=...)`.

- [x] Add red tests for wrong config/runtime/module paths, absent/changed manifests,
  wrong service/project binding, linked inputs and duplicate output use.
- [x] Implement fixed paths derived from the direct runtime and the schema1 config;
  verify both repository inventories/HEAD identities and auxiliary module hashes.
- [x] First tick records PID/current token SID, bounded PATH digest, resolved Git
  executable digest/version; the coordinator verifies the SCM PID/image/SID.
- [x] Perform product-style default, isolated default, selected trusted, other with
  selected trust, and selected default again, with distinct environment/argv receipts.
- [x] Write the complete result once, hold the service until SCM STOP, and record
  close. Failures retain a failure result and produce a nonzero service exit.
- [x] Run narrow tests and existing service-entry contracts; commit the worker slice.

## Task 3: Owned coordinator, actual SCM and cleanup

**Files:**
- Create `scripts/verification/verify_git_scm_diagnostic.py`.
- Create `scripts/verification/scm_git_diagnostic_control.py` for fixed SCM controls.
- Create `tests/unit/test_git_scm_diagnostic.py` for coordinator/control safeguards.
- Modify `.github/workflows/core-ci.yml` to add a separate diagnostic job and upload.

**Interfaces:**
- CLI consumes `--kit --build-receipt --expected-commit --output --run`, requiring
  the same accepted kit source/hash/offline-install evidence as the existing verifier.
- `DiagnosticInstaller` controls only `Rentgen.CI.<12hex>` and the fixed
  `python.exe -I -m scm_git_probe_service --service --config <owned service.json>`.
- `DiagnosticAcceptance` reuses baseline ACL/owner backup and finally cleanup from
  `scm_acceptance_worker.Acceptance`, with fixed diagnostic installer and exercise.

- [x] Red tests reject changed modules/runtime/manifest/repo paths and unknown
  existing service before any SCM/ACL mutation; timeout never implies created ownership.
- [x] Prepare the standard Source Observer fixture unchanged, plus two local repos
  with no remotes and an empty global-config file. Hash all extra scripts and inputs.
- [x] Preflight the standard fixture/runtime, then verify auxiliary module/input
  bindings and foreign owners. Require elevated SCM create/backup/restore authority.
- [x] Fixed adapter uses absolute SystemRoot/System32/sc.exe and query-before-create;
  verify exact config/account/type/name before every subsequent control operation.
- [x] Implement exercise: baseline ACL → create → RUNNING/PID/image/SID → raw probe result →
  STOP/STOPPED → source/ref/index/config bytes equal → finally delete/ACL cleanup.
- [x] Implement raw validation of all four isolated outcomes; preserve the default outcome as observed.
  Result fields `native_git_scm_accepted`, `continuous_git_accepted`,
  `production_trust_policy_selected`, `full_product_ready`, `production_deployment`
  remain false even when `diagnostic_accepted` is true.
- [x] Add a Windows CI job depending on the built kit, retain evidence with `always()`
  even on failed lifecycle, and run local contracts before push.
- [ ] Push/attach a draft PR with exact local tests and explicit pending native scope.
  Qualify actual checkout, installed payload, raw process/ACL/probe evidence from CI.

## Task 4: Evidence and next production slice

**Files:**
- Update this plan and continuous service plan only with actual accepted results.
- Create a public redacted diagnostic evidence JSON and detailed PR announcement.

- [ ] Download terminal CI artifacts/logs once, verify their hashes and raw fields;
  preserve unsuccessful outcomes and distinguish diagnostic from product acceptance.
- [ ] Publish detailed measured results with readback; keep the production trust
  policy unset until the actual evidence justifies a separate design.
- [ ] Then qualify stock schema3 GitAuditWorker with native BSL and subsequent Core
  payload through source/main/release checks and immutable release publication.

## Local Task 1 evidence

20 contracts passed with zero failures/errors/skips. Initial18 cases failed
because the module was absent. A real current-user Git case then found the
installed cmd/git.exe has two hardlinks; binary observation accepts that,
while owned config/raw inputs still reject hardlinks. That real Git case
confirmed exact root/commit, unchanged repository/global config and no
safe.directory persistence in the next process. Actual LocalService has
not been run for this diagnostic; production trust remains unset.

## Local Task 2 evidence

Fresh JUnit:34 probe/manifest/worker cases plus69 service-entry cases,
103passed/zero failures/errors/skips. Nine input cases and five worker/entry
cases were red before their implementation. Positive ownership flows use
injected unit observations; they do not prove LocalService. All worker
acceptance fields stay false until the owned coordinator validates actual
SCM/process/raw evidence and cleanup. Core/public installer bytes unchanged.

## Local Task 3 evidence

Implemented the fixed SCM adapter, auxiliary preparation/preflight, raw evidence
validator, inherited ACL/owner cleanup, host/direct-runtime CLI and separate
`native-git-diagnostic` job. Raw Git streams, result/close and fixed input manifest
are copied with bounded sizes and hashes into uploaded evidence, including failed
measurements. Cleanup failure prevents acceptance. The coordinator waits for
complete JSON when the writer has created a file but not finished writing it.

Fresh local JUnit: 61 coordinator/control contracts, 34 probe contracts and 43
existing SCM-verifier contracts: 137 passed, one skipped. The skipped native DACL
round trip requires backup/restore privileges absent from the local token; its
actual execution remains a CI gate. Positive LocalService flows in unit tests are
injected observations. Actual diagnostic SCM, stock schema3 Git/BSL, production
trust policy and subsequent Core release remain unaccepted. Existing public tags
and assets retain their prior payloads.
