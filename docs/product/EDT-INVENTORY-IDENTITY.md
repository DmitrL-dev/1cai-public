# Bounded EDT identity inventory

`rentgen_core.edt_inventory.edt_metadata_inventory(ctx, layer_id=None,
limits=EDTInventoryLimits())` is a read-only Python adapter over a published,
authorized snapshot. Existing runtime `inventory()` and `exported_inventory()`
APIs retain their contracts. The adapter does not run EDT or 1C, read a live
project, write files, or change the existing metadata endpoints.

## Local CLI

The development checkout exposes the same inventory through `rentgen edt-inventory`:

```powershell
rentgen edt-inventory --registry C:\work\registry.sqlite3 --project PROJECT_UUID --snapshot SNAPSHOT_ID --layer-id base
```

`--registry`, `--project` and `--snapshot` are required. The snapshot must be
published in the selected project; the command never defaults to the latest
snapshot. Later checkout edits and a newer project head do not change the
selected inputs. Omit `--layer-id` to inspect all declared layers; each selected
layer must use the `edt` format.

Only `project:read` is required. Authorization is checked before snapshot
resolution, before each retained manifest/source/derived/graph read during eager
generation verification (including the graph SQLite reopen), by the shared read
session before source access, after JSON
serialization, and before emitting errors. Revocation suppresses the result.
Resolution and inventory failures retain their stable error code with a fixed
CLI message and empty details, without source diagnostics or partial inventory.

All limits are positive integers and may only be lowered. Repeated options,
booleans, zero, negative values and values above these ceilings are rejected;
typed limits are validated before snapshot resolution.

| Option | Default and ceiling |
| --- | ---: |
| `--max-xml-bytes` | 4,194,304 |
| `--max-nodes` | 50,000 |
| `--max-depth` | 64 |
| `--max-inventory` | 20,000 |
| `--max-collection` | 200 |
| `--max-total-bytes` | 67,108,864 |
| `--max-asset-bytes` | 16,777,216 |
| `--max-mdo-files` | 2,048 |
| `--max-identities` | 20,000 |

Successful stdout is one UTF-8 JSON envelope with the unchanged inventory in
`result` and a `request_id`. The serialized envelope is capped at 8 MiB;
`OUTPUT_LIMIT_EXCEEDED` returns an error instead of truncated output. Errors
exit with code 2. Human-readable help is available through `--help`.

There are no output-file, caller-file, workspace, apply, operation or native
profile options. The command does not create a snapshot, write source/state
artifacts, materialize changes, or invoke EDT/1C. This transport preserves the
synthetic, partial evidence scope described below.

## Evidence and scope

The result uses `edt_identity_v1` for the legacy compact `.mdo` contract and
`edt_identity_v2` for actual EDT `MetaDataObject` XML. Both profiles report
`coverage: partial`. Each identity includes its normalized `canonical_uuid`,
original `observed_uuid`, type, name, XML location, verified `SourceRef`, and
the layer declaration pinned to the snapshot. UUID uniqueness is scoped to
`(layer_id, canonical_uuid)`. The same UUID in base and extension layers stays
two distinct observations; this does not establish adoption or override semantics.

Only the established root paths `Configuration/Configuration.mdo` and
`<known metadata folder>/<name>/<name>.mdo` are recognized. The root must have
the matching type and namespace `http://g5.1c.ru/v8/dt/metadata/mdclass`.
Non-configuration root names must match their path. UUIDs must use hyphenated
8-4-4-4-12 hexadecimal notation and must not be nil; uppercase is normalized
to lowercase. This is syntax and uniqueness validation, not proof of platform
identity or compatibility.

Direct embedded declarations supported by this profile are `attributes`,
`tabularSections`, `dimensions`, `resources`, `forms`, `commands`, and
`enumValues`. Within an embedded tabular section, direct attributes are also
supported. Their `owner` points to the immediate XML parent identity and its
SourceRef/XML location. The XML path indexes count all element children from
zero. Root objects have `owner: null`; a configuration owner is not inferred
from the directory tree. Names and declarations may be unqualified or use the
metadata namespace. Every identity requires one direct, nonempty identifier
name, at most 256 characters. The profile does not validate whether a metadata
type and every property combination are accepted by a particular 1C version.

### Actual EDT XML

The v2 profile reads the real EDT descriptor shape: a namespaced
`MetaDataObject` wrapper, one metadata root with `Properties/Name`, and direct
identity-bearing children under `ChildObjects`. It recognizes the same known
metadata folders in their `.xml` form, plus separate object forms and commands
at `<owner>/Forms/<name>.xml` and `<owner>/Commands/<name>.xml`. A separate
child descriptor is accepted only when its parent `.xml` descriptor is present
and has passed identity validation; the returned owner contains that verified
UUID and source reference. Parent form/command references without a UUID are
not reported as identities. Unknown UUID-bearing containers, foreign structural
namespaces, mixed `.mdo`/`MetaDataObject` files in one layer and missing owners
fail closed. The descriptor's `Properties/Name` must match its filename.

Non-metadata assets, including BSL, form implementation XML and templates,
contribute only to the `unparsed_files` manifest count. The adapter does not
infer their owner, parse their contents, or report their unverified bytes as
evidence. `source_refs` contains exactly the descriptor references used by the
returned identities. The generation validation summary comes from the shared
snapshot read session.

## Fail-closed behavior

- A layer without an explicit `edt` declaration, mixed Designer root candidates,
  unknown metadata paths, root/type/namespace mismatches, unknown
  identity-bearing elements and unsupported nested owners fail with
  `EDT_INVENTORY_UNSUPPORTED`.
- Invalid UUID/name or path/name bindings fail with `EDT_IDENTITY_INVALID`.
- Duplicate normalized UUIDs in one layer, or duplicate case-insensitive names
  of the same type under one XML owner, fail with `EDT_IDENTITY_DUPLICATE`.
- XML syntax, DTD/entity rejection, source tampering, authorization and revocation
  errors remain governed by the shared metadata parser and snapshot capability.
  No partial inventory is returned on failure.

The adapter inherits the metadata ceilings: 4 MiB per XML document, 50,000 XML
nodes, depth 64, 20,000 manifest entries and 64 MiB total read bytes. It adds
whole-operation limits of 2,048 MDO documents and 20,000 identities across all
selected layers. Callers may lower limits using `EDTInventoryLimits`; booleans,
zero, negative values and raised ceilings are rejected. Limits never silently
truncate successful output.

The v2 parser has contract tests against the saved real EDT descriptor shape;
the files are still a synthetic product fixture. Neither profile establishes
complete EDT inventory coverage, reference resolution, extension semantics,
native round-trip compatibility or support for typical configurations and all
object types.
