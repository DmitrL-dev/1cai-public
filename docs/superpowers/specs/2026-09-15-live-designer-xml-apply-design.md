# Live Designer XML apply — design

## Goal

Provide the first product writer for the already supported
`rename_catalog_attribute` proposal. It applies a retained candidate directly
to a registered source tree only when the tree is one base `designer_xml` layer,
the candidate changes existing files only, and every changed path is bound to
the exact retained preview.

## Contract

`apply_live(ctx, operation_id)` reauthorizes `project:read`, `source:edit` and
`analysis:run`, reloads the preflight and preview, and compares the complete
current source inventory with the preview's `original` inventory. The candidate
must have the same paths and differ only in the supported preview edit. The
writer returns a sealed receipt with before/after digests and changed paths.

`undo_live(ctx, operation_id)` is an explicit compare-and-swap operation. It
restores only files recorded in the apply receipt and only when the complete
source inventory still equals the receipt's after state. Any foreign change
causes a conflict and leaves the source untouched. An interrupted operation is
reported as `OUTCOME_UNKNOWN`; `recover_live(..., target="original")` uses the
sealed backup and never replays the proposal.

## Storage and safety

The journal lives outside the source tree under `metadata-live-apply/<UUID>`.
An OS file lock serializes live writers for the project. Backups and staged
candidate files are written and fsynced before any `os.replace`; each boundary
rechecks authorization and path identity. The implementation never invokes
Configurator, EDT, a model, or a network service.

## Deliberate limits

The first slice does not claim support for binary `.cf/.cfe`, EDT `.mdo` or
`MetaDataObject` XML, extensions, new/deleted objects, or candidate
normalization changes. Those remain blocked until their own producer and
rollback evidence exist.

## Verification

Unit tests cover successful apply/undo, stale source, foreign edits, lock
contention, tampered receipts, interrupted publication and explicit recovery.
The existing full suite and the installed 1C fixture smoke remain required.
