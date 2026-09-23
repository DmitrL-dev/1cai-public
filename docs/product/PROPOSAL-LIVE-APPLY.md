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

## Installed dev9 and native 1C check

On 23 September 2026, the published core `0.1.0.dev9` offline kit was installed
with locked wheel hashes on a fixed local Windows volume. Its archive SHA256 is
`5615383c3985c4c3144eb636424157619dab959f0a30af7003cc8c88a21c58d9`.
The [repeatable verifier](../../scripts/verification/verify_proposal_platform_delivery.py)
used that installation, the kit's scanner, and 1C 8.3.27.2342 with executable
SHA256 `2a9ef3653367b6de29000a3a51749a19e6450134347925713c9075674e9f0956`.
Its new `--exercise-live` mode requires matching `--expected-core-version` and
`--expected-platform-sha256` pins. Inputs are an independently created
`first-roundtrip` Designer XML fixture and a new output directory on a fixed
local volume; the script refuses to reuse an existing output directory.

The installed CLI created and retained one proposal for an existing common
module. The native proposal precheck passed for valid BSL and found diagnostics
for an intentionally broken version. The CLI then applied the valid proposal to
its **owned copy** of the source tree. A new file infobase loaded those exact
applied bytes, passed `/CheckConfig`, updated the database, and returned **43**
when the application executed. The exported module text and both configuration
and module UUIDs matched. After `proposal-live-undo`, the complete owned source
inventory returned to its original hashes. Reloading it into the same test
infobase passed compilation and execution returned **42**. The project head was
unchanged. No model call or production deployment occurred.

The [bounded receipt](evidence/proposal-live-native-dev9-20260923.json) binds the
release archive and wheel, verifier commit, platform binary, source hashes,
operation/result IDs, runtime values, and 11 native steps. The
[raw verifier result](evidence/proposal-live-native-dev9-20260923.raw.json)
is also retained with its SHA256 in that receipt; local paths and platform logs
are not published. This check covers one synthetic common module on one
installed 1C version. It does not qualify typical configurations, extensions,
forms/СКД, a live production infobase, or concurrent external writers.

## Installed dev10 follow-up on native 1C

On 23 September 2026, the same repeatable verifier was run against the
published core `0.1.0.dev10` offline kit, SHA256
`11d5f8e850eec13d9a67c9cd1985db212a076e882b8794cb790fb7ac2dbee4e3`.
The wheel was installed from that kit with locked hashes on a fixed local
Windows volume. An independently accepted synthetic `first-roundtrip` Designer
XML fixture and a **new** local file infobase were used. The 1C executable was
version `8.3.27.2342`, SHA256
`2a9ef3653367b6de29000a3a51749a19e6450134347925713c9075674e9f0956`.

The installed CLI accepted valid BSL and reported diagnostics for the broken
candidate. It applied the valid proposal to its owned source copy. The native
platform loaded those exact bytes, passed `/CheckConfig`, updated the database,
and application execution returned **43**. An export matched the applied module
text and both UUIDs. After CLI Undo, the full owned source inventory returned
to its original hashes. Reload, `/CheckConfig`, database update, and application
execution returned **42**; the project head was unchanged. All 11 native steps
exited successfully without timeout, and no model was called.

The [bounded receipt](evidence/proposal-live-native-dev10-20260923.json) binds
the published archive and wheel, source and verifier commits, fixture report,
platform binary, source hashes, operation IDs, runtime values, and native steps.
The [raw verifier result](evidence/proposal-live-native-dev10-20260923.raw.json)
is retained with SHA256 `48c0deed591d38c38e3790c2e8df6ef382b12ae69079d9246d302dc118df946d`;
local paths and platform logs are not published. This is one synthetic common
module on one installed 1C version. Typical configurations, extensions,
forms/СКД, a live production infobase, external concurrent writers, and
production deployment remain outside this check.
