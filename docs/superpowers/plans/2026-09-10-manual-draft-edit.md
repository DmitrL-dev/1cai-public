# Manual correction of saved drafts

The failed AI proposal must be correctable from the editor without another model
request. Open an owned working copy of an exact saved revision. Save the local
document, then explicitly publish a new draft revision with the core's optimistic
revision check. Never write the live configuration or select a newer snapshot.

Persist numbered operation attempts before mutation, including expected receipt,
proposal ID and content hash. A lost response is recovered by operation receipt;
an unresolved operation blocks further saves in that session. A committed attempt
may be followed by another edit and save. Unchanged bytes must not add a revision.
Conflicts retain the working copy so the user can compare with the current draft.

Bound sessions, attempts and file sizes; use only derived owned paths, refuse
links, and preserve original BOM/line endings through ordinary editor file saving.
Only the active document belonging to a known edit session may be published.

Test conflict/lost reply/concurrent saves/trust loss, UI selection and file routing.
In the real packaged editor, correct the failed AI revision without a model,
save the next revision, run native compilation, independently check BSL, and
verify old history and live source remain unchanged. Keep overall readiness open.
