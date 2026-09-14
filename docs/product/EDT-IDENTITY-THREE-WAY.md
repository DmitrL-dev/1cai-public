# EDT identity three-way evidence

`rentgen edt-inventory-plan` compares three saved EDT identity inventories and
returns a deterministic, read-only plan. Coverage is **partial**. The plan is
review evidence: it creates no snapshot, candidate, source file or 1C change.
Materialization and native validation are unavailable.

## Inputs and CLI

Save the `result` object from each successful `rentgen edt-inventory` response
as a separate UTF-8 JSON file. Pass that object unchanged, without the outer
CLI envelope. The producer profile is `parser: edt_identity_v1`; there is no
input `schema` field. For example, extract an existing response in Python:

```python
import json
from pathlib import Path

response = json.loads(Path("base-response.json").read_text(encoding="utf-8"))
Path("base.json").write_text(
    json.dumps(response["result"], ensure_ascii=False), encoding="utf-8"
)
```

Repeat for current and upstream, then run:

```powershell
rentgen edt-inventory-plan --registry C:\state\registry.sqlite --project PROJECT_UUID --base-json base.json --current-json current.json --upstream-json upstream.json
```

The command requires `project:read` for the specified project. It checks rights
before every input read, after reads and decoding, before result serialization,
after serialization, and before error emission. Revocation prevents subsequent
input reads and suppresses stale evidence. Errors contain stable codes and
fixed messages without input payload. The command has no snapshot, source-root,
output, workspace, apply, operation-id or native-profile option.

All three project IDs must match the authorized project. Snapshot IDs normally
differ; each version must bind its own snapshot, source references and generation
summary consistently. The complete producer object includes `snapshot`, profile
fields, `layers`, `objects`, `source_refs` and `validation_summary`. Unknown
fields, duplicate keys/identities/layers, invalid UUIDs/hashes, ambiguous paths,
missing owners and fabricated coverage are rejected before any plan is returned.

Layers use the producer's `SnapshotLayer` fields: `layer_id`, `ordinal`, `kind`,
`configuration_uuid: null`, `identity_status: unresolved`, `source_format: edt`.
Top-level layer rows also contain file counts and `count_basis`. There is no
root-relative-path field. Each identity preserves its UUID, observed UUID, type,
name, XML location, direct owner, layer and `source_ref.raw_sha256`. The producer
has no per-source byte size: output `source_size_bytes` is always `null`.

The planner checks the supplied evidence's consistency. It does not reopen
snapshots or authenticate saved JSON against the original source files.

## Actions and identity bindings

Rows are keyed by `(layer_id, canonical_uuid)` and sorted by the lowest observed
layer ordinal, then layer ID and UUID. Snapshot IDs and observed UUID letter
case do not create changes. The comparison includes name, type, owner UUID/path,
XML location, layer declaration, source path and whole-file SHA-256.

| Action | Meaning |
| --- | --- |
| `unchanged` | All three identity projections match. |
| `same_change` | Current and upstream match each other and differ from base. |
| `keep_current` | Only current changed. |
| `take_upstream` | Only upstream changed. |
| `conflict` | Current and upstream differ, including delete/modify overlap. |
| `unsupported` | Identity binding or retained evidence is insufficient. |

An absent version is represented by `null`, so addition/deletion uses the same
action vocabulary. Root absence requires retained layer evidence. Child absence
also requires its direct owner in that version. Rename preserves UUID identity;
a changed owner source/XML path makes affected child rows unsupported.

Stable unsupported reasons are `layer_changed`, `type_changed`, `owner_changed`,
`owner_path_changed`, `missing_layer_evidence` and `missing_owner_evidence`.
UUID reuse across changed layer/type/owner bindings cannot become an ordinary
addition/deletion. A UUID consistently observed in two separate layers remains
two rows; the planner does not infer a cross-layer relationship.

Whole-file hashes are conservative: editing one sibling can change the evidence
for every identity in that file. This is not a property merge or a proof of
independent changes. No XML, BSL, form or СКД payload is returned.

## Bounds and API

| Option / API limit | Fixed ceiling |
| --- | --- |
| `--max-input-bytes` / `max_input_bytes` | 8 MiB per input |
| `--max-objects` / `max_objects` | 20,000 |
| `--max-owners` / `max_owners` | 20,000 |
| `--max-layers` / `max_layers` | 64 |
| `--max-rows` / `max_rows` | 20,000 |

Limits accept positive integers and may only lower these ceilings. Object,
owner and layer budgets apply per input and across the union. Serialized output
is capped at 8 MiB, including the CLI envelope; overflow returns
`OUTPUT_LIMIT_EXCEEDED` with no partial result. Malformed evidence returns
`EDT_IDENTITY_PLAN_INVALID`; comparison budgets return `EDT_IDENTITY_PLAN_LIMIT`.
The transport rejects malformed JSON with `INVALID_ARGUMENT`.

```python
from rentgen_core import EDTIdentityThreeWayLimits, plan_edt_identity_three_way

plan = plan_edt_identity_three_way(
    base, current, upstream, limits=EDTIdentityThreeWayLimits(max_rows=1000)
)
```

The pure API captures caller mappings once into private values and performs no
I/O. Its result has `schema: 1`, `scope: edt-identity-v1`, `mode: read_only`,
`coverage: partial`, `materialization: unavailable`, `native_validation:
unavailable`, per-version snapshots/canonical JSON digests, counts and identity
rows. Digests include the complete captured input, including list order and
generation evidence; they do not identify an executable candidate.

## Qualification boundary

Regression coverage includes a direct round trip from the existing published
synthetic EDT fixture through `edt_metadata_inventory` and this CLI, all six
actions, owner/layer/type changes, malformed/mutable input, lower budgets,
authorization revocation and output limits. This evidence does not qualify a
typical configuration, arbitrary extensions/forms/СКД, `.cf/.cfe` compatibility
or live apply. See [inventory](EDT-INVENTORY-IDENTITY.md) and the narrower
[Catalog attribute evidence](EDT-ATTRIBUTE-THREE-WAY.md).
