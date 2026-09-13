# Bounded EDT identity inventory

`rentgen_core.edt_inventory.edt_metadata_inventory(ctx, layer_id=None,
limits=EDTInventoryLimits())` is a read-only Python adapter over a published,
authorized snapshot. Existing runtime `inventory()` and `exported_inventory()`
APIs retain their contracts. The adapter does not run EDT or 1C, read a live
project, write files, or change the existing metadata endpoints.

## Evidence and scope

The result uses parser profile `edt_identity_v1` and always reports
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

Non-MDO assets, including BSL, forms and templates, contribute only to the
`unparsed_files` manifest count. The adapter does not infer their owner, parse
their contents, or report their unverified bytes as evidence. `source_refs`
contains exactly the MDO references used by the returned identities. The
generation validation summary comes from the shared snapshot read session.

## Fail-closed behavior

- A layer without an explicit `edt` declaration, mixed Designer root candidates,
  unknown MDO paths, root/type/namespace mismatches, unknown identity-bearing
  elements and unsupported nested owners fail with `EDT_INVENTORY_UNSUPPORTED`.
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

This profile has synthetic unit evidence. It does not establish complete EDT
inventory coverage, reference resolution, extension semantics, native round-trip
compatibility or support for typical configurations and all object types.
