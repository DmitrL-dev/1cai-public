# Git/snapshot source evidence

`Observer.verify_git_snapshot(observation) -> GitSnapshotEvidence | None` binds a
published snapshot to an observed local Git commit through the registered source
configuration. It reads no business metrics and does not run an analyzer, 1C or
EDT. The immutable value contains project ID, the exact repository/commit/ref
observation, snapshot ID and source digest. Constructing this value alone is not
verification.

Verification requires the observation repository to equal the resolved registered
source root. A clean tracked Git observation must equal the supplied observation
before and after the existing `probe_sources` operation. That probe uses confined
source reads, two matching content passes and stable inventory/configuration/head
checks. The published `head.snapshot` must be present in the catalog and its
`source_digest` must match the probed digest. The Observer rechecks the published
head around the Git checks and reauthorizes access before returning.

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

`owner_report(snapshot_id)` adds `quality.provenance: git_source_verified` only
when durable evidence agrees with the current finding observation, explicit
snapshot binding and catalog source digest. A manual `snapshot_id` association
continues to produce `caller_asserted`. Unbound findings remain unavailable as
snapshot quality. These markers supply no runtime or business values; without a
runtime adapter business metrics remain unavailable.

This is bounded workspace association, not a complete Git tree proof. A clean
tracked workspace plus the configured source digest associates a snapshot with
the observed commit. No full Git tree hash is calculated. Untracked/ignored files
outside the configured source coverage are not proven; included untracked files
can contribute to the source digest without becoming committed Git content.
Excluded files, Git filters, submodule internals and transient changes between
checks are not a guarantee of byte-for-byte commit tree identity. Verification
is temporal sampling, not an atomic filesystem or Git transaction. The local
observer database remains trusted storage, not a signed attestation boundary.

Tests use real local Git repositories, real published snapshots and the existing
confined source probe. They cover no snapshot, digest mismatch, repository and
HEAD races, changed tracked sources during analysis, persistence/historical
replay, legacy migration, corrupt evidence/schema, capacity rollback and owner
report provenance. No native 1C, EDT or Spectorn execution is needed.
