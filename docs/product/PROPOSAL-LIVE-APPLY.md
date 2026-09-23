# Direct BSL proposal apply

The public development branch contains a deliberately narrow live writer for
one existing `.bsl` file in the registered **base Designer XML** source layer.
It applies an already validated proposal, records a sealed before/after
inventory, and uses the same project lock as the metadata live writer.

The operation is a filesystem source-tree change. It does not open 1C, invoke
Configurator, update a `.cf/.cfe`, or prove that a database can run the result.
Run the native platform check and the required tests before treating a proposal
as release-ready.

The writer checks all of the following before the first write:

- the caller has `project:read`, `source:edit`, and `analysis:run`;
- the exact project head supplied by the caller is still current;
- the proposal is revalidated against its retained snapshot and source hash;
- the configured base layer is Designer XML and the target is an existing
  regular BSL file under the registered root;
- the source tree and state-root are on the same filesystem volume (the
  journal stage is published with `os.replace`, which cannot cross volumes);
- the current complete source inventory equals the retained source bytes; and
- the replacement is not a no-op.

Each operation is journaled below `state-root/proposal-live-apply/<operation-id>`.
The journal contains a canonical intent, a backup, staged replacement bytes, and
sealed state/result records. A failure during `os.replace` leaves the operation
as `OUTCOME_UNKNOWN`; callers must inspect status and explicitly request
`recover_live(..., target="original")`. Undo uses a compare-and-swap against the
confirmed after-inventory and refuses to overwrite foreign source bytes.
An interrupted Undo or Recover also reports `OUTCOME_UNKNOWN` until a terminal
state matches its sealed result ID. Recover can be repeated after an interrupted
replacement: it validates the owned recovery stage, restores consumed files
from the sealed backup, and resumes. Unexpected stage entries or a changed
same-size staged file fail closed for operator inspection. A cross-volume
source/state layout is refused before creating a live journal; it does not
silently fall back to a non-atomic copy.
Recover first reconciles a sealed temporary state or terminal result left by an
interrupted journal replacement. It checks the operation binding, receipt ID,
and expected source inventory before promoting the record. Malformed or
conflicting temporary records remain blocked for operator inspection.

Python API aliases are exported as `apply_proposal_live`,
`undo_proposal_live`, `get_proposal_live_status`, and
`recover_proposal_live`. The local CLI exposes:

```text
rentgen proposal-live-apply   --registry ... --project ... --snapshot ... \
  --operation-id ... --proposal-json proposal.json --expected-head-json head.json
rentgen proposal-live-undo    --registry ... --project ... --operation-id ...
rentgen proposal-live-status  --registry ... --project ... --operation-id ...
rentgen proposal-live-recover --registry ... --project ... --operation-id ... \
  --target original
```

This is an early-access capability. Extensions, forms, СКД, arbitrary metadata
operations, live information bases, and external concurrent writers remain
outside the accepted scope.
