# Durable project drafts and proposal history

Design implemented in the development checkout, 2026-09-09. The workflow lets a user save a draft,
close the browser, reopen it under current project authorization, inspect its
versions and continue editing without overwriting another editor's work.

Implementation checkpoint: schema4/bootstrap, verified3→4 migration, core
save/read/history/archive/restore/receipt, local CLI and [HTTP endpoints](PROJECT-DRAFTS-HTTP.md)
are implemented in the development checkout. See [the runbook](DRAFT-HISTORY.md).
[Browser persistence, recovery and discard protection](DRAFT-EDITOR.md) are
implemented and accepted on the real scoped API. A rebuilt distribution remains pending.

## Storage decision

Store shared project drafts in the existing project SQLite file. Use its
`StateTransaction` for authorization, compare-and-swap, revision insertion and
operation receipt in one commit. A browser cache or a second database would
introduce a separate authorization/commit boundary and cannot provide this
contract. A locally downloaded file remains an explicit export, not history.

Schema 4 will deliver the complete draft/history contract below. The broader
[workflow ADR](WORKFLOW-STATE-ADR.md) remains the target for profiles, trusted
runs, approvals and effects. Their execution contracts, including completion
after caller revocation, need separate implementation and an explicit later
schema migration. Do not create unused tables with permissive placeholder JSON
columns or silently add them to an existing schema-4 database.

## Schema and invariants

- `workflow_receipts`: project + operation UUID, action/version, actual actor,
  timestamp and canonical bounded request/result. It is a separate receipt
  family; publication and administrative receipt decoders keep their contracts.
- `workflow_proposals`: project + content ID, complete canonical proposal bytes,
  exact snapshot/layer/path/raw hash and candidate hash/size. References the
  retained project snapshot through composite foreign keys.
- `workflow_draft_heads`: project + draft UUID, current revision. A head points
  to an existing immutable revision; it never points to a partially saved value.
- `workflow_draft_revisions`: project + draft UUID + monotonic revision,
  proposal content ID, bounded title, active/archived state, actor and operation
  receipt. Each revision retains its full source binding through its proposal.

Every save validates the supplied canonical proposal through the core against
retained source bytes before the SQL write transaction. The transaction checks
fresh `project:read` and `source:edit`, schema, referenced snapshot and expected
draft revision. File parsing/analyzers do not run while holding its write lock.
A DTO or a client-supplied diagnostic result is never execution evidence.

Drafts are project artifacts: current readers may inspect them; writers with
`source:edit` may save or archive them. An archive is a new revision and retains
history. It does not delete the original module or imply that a change was
applied. Use an explicit restore operation to reopen an archived draft.

The first save expects revision 0; subsequent saves supply the exact observed
revision. A conflict returns an explicit error and leaves both stored state and
the local draft intact. Reusing an operation UUID with the same actor and exact
request returns the original receipt after fresh authorization. Different
content/actor under that UUID conflicts. A lost acknowledgment is reconciled by
that UUID, never by issuing a new save automatically.

Ordinary saves keep the same full SourceRef. Moving a draft to another snapshot
requires a future explicit rebase operation with its own checks and history.
The schema retains a SourceRef per revision so that future rebase does not erase
the old binding. It must not silently follow the latest head.

Canonical proposals are limited to 1.5 MiB; original/candidate remain at most
1 MiB. Titles are bounded plain text. Lists contain bounded metadata pages,
not every revision's source bytes. Fetch proposal bytes by an explicit version;
corrupt stored JSON, hashes, cross-project bindings or missing relationships
fail closed. Source validation is repeated when creating a new proposal or
rendering/checking a stored one. Historical storage does not certify that
retained filesystem artifacts can never be corrupted later.

## Delivery and acceptance

1. Extend the verified backup path to actual schema 3, including WAL contents,
   administrative receipts and exact required table constraints; keep its files
   pinned through the following migration and final acknowledgment.
2. Add explicit schema3→4 migration with a workflow upgrade receipt, rollback
   before commit and exact-operation reconciliation after uncertain completion.
   Preserve old snapshots, administrative history and published hashes. Switch
   fresh bootstrap to 4 only with tested readers and the explicit CLI upgrade.
3. Implement core save/get/list/history/archive/restore with fresh membership,
   immutable revisions, CAS and receipts. Verify concurrency, replay, collision,
   malformed/cross-project proposals and revocation on real SQLite.
4. Expose scoped CLI/HTTP operations; preserve the server's bounded request and
   final authorization rules. The browser retains operation IDs across explicit
   reconciliation and never labels an uncertain save as completed.
5. Connect editor save/open/version history. Verify actual save → browser close
   → login/reopen → edit, another writer's conflict, project switching and loss
   of access. Add discard protection for unsaved local changes.

These are delivery increments, not alternative completion criteria. Whole-
snapshot module search, complete AI development, trusted platform tests,
reviewed apply/undo, metadata/forms editing, update preservation, continuous
audit/business reports, offline distribution and pilot evidence remain required
by the product goal. Platform execution stays deferred until the user installs
1C; independent workflow implementation proceeds now.
