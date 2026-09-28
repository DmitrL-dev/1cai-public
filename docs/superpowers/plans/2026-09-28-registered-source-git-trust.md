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
- [x] Verify the seven affected regression suites, document the explicit setting,
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

Task1/2 published as dcff/e902 after both original d96 attempts completed and
were raw-qualified. The 31-path PR description and detailed announcement
https://github.com/DmitrL-dev/1cai-public/pull/41#issuecomment-5863528823
were read back anonymously together with both public local JSON records.
The same e902 push36378651630/PR36378654533 attempts continue; do not restart
them when observation times out. Native/source/main/new-version acceptance
remains pending.

## Task 3 — production capture and actual native qualification

- [x] Bound production stdout during reading, preserve command-specific error
  codes, timeout and same-child reap; add overflow/timeout tests using actual
  child processes before integrating that boundary.
- [ ] Prepare an installed stock schema 3 fixture with actual foreign owners,
  native BSL runtime, real Git and raw SCM/process/ACL proofs.
- [ ] Verify exact commit capture/history, STOP/recovery, no source mutations and
  cleanup in privileged Windows CI. Keep unsuccessful raw artifacts.
- [ ] Qualify source/main/new Core release and publish detailed immutable assets
  with anonymous readback. Full product gaps remain separate; no deployment.

Task3 capture slice: 20 contracts were red before the API. The first helper run
passed 20 cases, including ten actual current-user Windows Python children and
ten prelaunch/no-child cases. Integration passed 156 cases. Root inspection
then found a possible lost final write between an empty peek and exit poll.
The explicit injected race was red (1 failed /20 passed), and polling exit before
peeking made all 21 helper cases green. This is one injected race case, not an
additional native child proof. The final nine relevant suites passed 290 cases
in 318.51s, zero failures/errors/skips, including 32 new capture/mapping/real-Git
overflow cases and all 56 preceding trust/service cases. The unchanged entry
configuration and long durable-journal suites were already included in Task2's
371-pass run and were not repeated for this capture-only change.

The reader retains at most the command bound plus one byte, creates no reader
thread, kills/waits on the same child and closes stdout on overflow/timeout.
Actual oversized committed blob and a reduced-bound real listing fail before
BSL without repository mutation. Error mappings and history rewrite semantics
remain. Public local record:
`docs/product/evidence/registered-source-git-capture-local-20260928.json`.
The local capture commit is deliberately kept separate from the still-running
e902 remote source CI; its own push/source/native/new Core acceptance is pending.


Stock SCM preparation prerequisite: the original SourceObserver fixture remains
exactly five source entries by default. An explicit coordinator-supplied manifest
now allows Git metadata inside that same registered source root and compares the
complete inventory, directory flags, file sizes and SHA256 values. Names cannot
escape the fixed BSL layout or `.git`; Git root/HEAD/config/index are mandatory.
The source module stays bound to the original fixture digest. This is a verifier
argument; service JSON cannot select a manifest or relax registered-root policy.

TDD: all 27 new source-manifest contracts were red before the helper, then all
27 passed, including one real current-user Windows Git fixture and metadata hash
refusal. The final new/existing SCM verifier run was 69 passed /1 skipped;
the single existing native DACL test requires backup/restore privileges and is
exercised separately by elevated CI. This local run performs no SCM create/start,
no LocalService BSL execution, and grants no native or full-product acceptance.
Public record: `docs/product/evidence/stock-scm-source-manifest-local-20260928.json`.
The e902 original CI attempts remain unchanged; stock native composition is still
pending and the later capture/manifest source needs its own CI qualification.


Stock control/ACL prerequisites: the verification-only adapter retains the public
ServiceInstallSpec for `python.exe -I -m rentgen_core.service_entry --service`
with one fixed owned schema3 config. It hashes interpreter/config/source-manifest/
installed stock entry, retains bounded raw System32 sc.exe controls and reuses
the diagnostic adapter's acknowledged-create, authority, exact-binding and
unknown-outcome refusal guards. No diagnostic module is the new SCM ImagePath.
The coordinator must still bind verifier source hashes and installed wheel bytes.

Temporary ACL preparation now has a separate stock policy for exactly the fixed
data and diagnostics scratch trees. Original Git source, JDK/JAR, runtime and
all other fixture entries stay read/execute. Exact protected ACE validation is
applied to both partitions; the original SourceObserver ACL verifier is unchanged.
Native owner/DACL restoration and descendant cleanup remain mandatory gates.

TDD: 21 new control contracts and 14 new ACL contracts were red before their
APIs. Final four-suite regression: 138 passed /1 existing privileged DACL skip.
Control observations are injected; ACL tests construct/validate descriptors and
perform no native grants. This proves local prerequisites, not stock SCM/BSL
acceptance. Public record: `docs/product/evidence/stock-scm-control-acl-local-20260928.json`.
Pinned upstream metadata was inspected: BSL exec JAR bytes131962428; JDK ZIP
bytes205073461 with the checked-in archive hash. Java profile size343823876 is
the sum of all 490 installed manifest file sizes, not ZIP length. Preparation
will reuse the checked-in local-file installer and avoid a Java warm-up run.
