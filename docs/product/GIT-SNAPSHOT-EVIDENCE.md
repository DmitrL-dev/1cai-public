# Git/snapshot source evidence

`Observer.verify_git_snapshot(observation) -> GitSnapshotEvidence | None` binds a
published snapshot to an observed local Git commit through the registered source
configuration. It reads no business metrics and does not run an analyzer, 1C or
EDT. The immutable value contains project ID, the exact repository/commit/ref
observation, snapshot ID, source digest and `tree_binding`. Constructing this value alone is not
verification.

Verification requires the observation repository to equal the resolved registered
source root. A clean tracked Git observation must equal the supplied observation
before and after the existing `probe_sources` operation. That probe uses confined
source reads, two matching content passes and stable inventory/configuration/head
checks. The published `head.snapshot` must be present in the catalog and its
`source_digest` must match the probed digest. The Observer rechecks the published
head around the Git checks and reauthorizes access before returning.

Current sources also resolve the exact `commit^{tree}` and compare each captured
file outside the repository's own `.git` with the regular blob at the same
repository path. The session supplies verified layer roots and retained bytes.
Git SHA-1/SHA-256 blob hashes include the canonical blob header; no line-ending
or filter normalization is applied. Included untracked/ignored files, changed
bytes, duplicate paths, symlinks and gitlinks fail with `GIT_TREE_MISMATCH`
before analysis. A failed or oversized Git listing gives `GIT_TREE_PROBE_FAILED`.
Replacement refs are disabled; the listing is bounded to 64 MiB and each Git
command to 30 seconds, alongside the existing retained-session budgets.

No published snapshot returns `None`; GitWatcher reports
`snapshot_binding: unbound_no_snapshot`. A digest mismatch raises
`GIT_SNAPSHOT_MISMATCH`; a repository mismatch raises `GIT_SNAPSHOT_CONTEXT`.
Git/source/head races propagate explicit `CoreError` failures. No report is
recorded after a failed verification.

For a new commit, GitWatcher verifies evidence before invoking its analyzer,
checks Git HEAD again afterward, and passes the evidence to
`record_findings(report, evidence=evidence)`. The analyzer still owns the complete
finding report; evidence does not attest that an analyzer ran or that findings
are correct. Before saving new evidence, `record_findings` checks its context and
catalog digest and repeats live verification. This also rejects a fabricated
value or stale source association. A matching historical evidence replay uses its
already saved receipt and does not require checking out the historical commit.

Evidence is saved in `git_snapshot_evidence`, separately from the existing
`finding_binding`. Each commit has at most one immutable evidence receipt:
conflicting replays fail closed. Evidence, findings and snapshot binding commit in
one SQLite transaction. Limits are 10,000 evidence rows, 32 KiB per JSON receipt
and 64 MiB total evidence JSON. Exhaustion retains history and raises
`OBSERVER_JOURNAL_FULL`.

Observer findings schema versions 0 and 1 migrate transactionally to version 2.
Existing findings, receipts and manual bindings are preserved. Existing manual
bindings gain no verification evidence during migration. Version 2 requires the
expected evidence table structure; missing or incompatible structure fails
closed. Malformed evidence or a disagreement with report/catalog context is
rejected rather than promoted to verified quality.

Legacy evidence without `tree_binding` remains readable and replayable with
its original scope. New evidence requires binding schema 1; unknown or malformed
binding shapes are refused. The binding records object format, exact tree ID,
matched file count, excluded `.git` file count and
`tree_entries_outside_snapshot` inside the configured layer roots. Missing
snapshot coverage is counted, not promoted to proven content. GitWatcher emits
the verified tree ID and owner-report quality includes the binding when present.

`owner_report(snapshot_id)` adds `quality.provenance: git_source_verified` only
when durable evidence agrees with the current finding observation, explicit
snapshot binding and catalog source digest. A manual `snapshot_id` association
continues to produce `caller_asserted`. Unbound findings remain unavailable as
snapshot quality. These markers supply no runtime or business values; without a
runtime adapter business metrics remain unavailable.

This proves the matched captured files, not complete repository coverage.
Excluded files, submodule internals and entries outside the configured source
coverage remain unproven. Git filters or line-ending conversion that make a
captured file differ from its blob cause a refusal, even when Git reports a
clean worktree. Transient changes between checks remain outside the proof. Verification
is temporal sampling, not an atomic filesystem or Git transaction. The local
observer database remains trusted storage, not a signed attestation boundary.

Internal `GitRepositoryTrust` optionally accepts a canonical executable path
and SHA-256 together. Trusted commands hash that file before constructing argv
and reject changed bytes with `GIT_EXECUTABLE_MISMATCH`. This pins one file only;
DLLs/helpers and the hash-to-spawn interval remain the host's responsibility.
The existing host configuration does not automatically enable this optional pin.

Tests use real local Git repositories, real published snapshots and the existing
confined source probe. They cover no snapshot, digest mismatch, repository and
HEAD races, changed tracked sources during analysis, persistence/historical
replay, legacy migration, corrupt evidence/schema, capacity rollback and owner
report provenance. No native 1C, EDT or Spectorn execution is needed.
