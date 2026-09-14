# Read-only EDT Catalog attribute three-way evidence

`rentgen_core.plan_edt_attribute_three_way(base, current, upstream)` compares
direct attributes of explicitly selected EDT Catalog descriptors. It accepts
three mappings of repository-relative paths to immutable `bytes`, performs no
filesystem or 1C/EDT operations, and returns evidence only. It never returns a
candidate, merges XML, or authorizes apply.

The input subset contains only `Catalogs/<name>/<name>.mdo` entries. Callers
must select this subset explicitly; a complete EDT tree or an unknown path is
rejected rather than silently treated as a supported configuration. Empty
selections are allowed. These caller-selected byte trees do not establish a
snapshot, SourceRef, layer, extension ownership or trusted producer binding.

## Supported projection

The root must be `Catalog` in
`http://g5.1c.ru/v8/dt/metadata/mdclass`. Its direct `name` must match both the
directory and file stem. EDT represents the selected children as direct
`attributes` elements with a `uuid` attribute and direct `name`; there is no
Designer `ChildObjects/Attribute/Properties` wrapper in this format.

Root UUIDs and child UUIDs are required, canonicalized to lowercase, and must
be nonzero UUID-shaped values. Child identity is independent of its name.
Names use the existing EDT identifier shape and a 256-character bound. Direct
child elements may be unqualified or use the metadata namespace. A foreign
namespace on an identity or its direct properties is rejected.

Only direct Catalog attributes receive rows. Known direct `forms`, `commands`
and `tabularSections`, including attributes directly below a tabular section,
are validated for identity uniqueness and containment but receive no rows.
This does not qualify their content, behavior or merge semantics. Unknown or
indirect UUID-bearing declarations and extension ownership declarations are
rejected. Each selected identity permits only the `uuid` XML attribute.

Duplicate UUIDs anywhere in a selected tree, duplicate case-insensitive names
of one child kind under one direct owner, ambiguous/missing names, duplicate
direct Attribute property names and mixed text outside those properties fail
the entire operation. Malformed XML, DTD/ENTITY declarations, comments and
processing instructions also fail closed. DTD scanning covers UTF-16/32 layouts
before parsing; an unsupported encoding produces a structured error.

## Output and actions

The result contains `schema: 1`, `scope: edt-catalog-attributes-v1`,
`mode: read_only`, `coverage: partial`, `owner_basis: direct_xml_containment_only`,
three exact input tree digests and a deterministic `child_objects` list ordered
by canonical child UUID.

Each row has `child_type: Attribute`, `child_uuid`, `action`,
`property_mergeability`, `property_changes`, and `base`, `current`, `upstream`.
Each version is either `null` for an absent attribute, or:

- `name`;
- `owner`, containing the direct Catalog `type`, canonical `uuid` and descriptor
  `path` from that version;
- `xml_path`, such as `/Catalog/attributes[1]`, whose bracket is the zero-based
  index among **all** direct Catalog XML children;
- `sha256` and `size_bytes` of the structural projection described below;
- `source_sha256` and `source_size_bytes` of the exact descriptor bytes.

`action` compares the projected attribute content, using `unchanged`,
`same_change`, `keep_current`, `take_upstream` and `conflict`. Additions and
deletions are represented by missing version records; delete/modify yields
`conflict`. Rename keeps the same UUID row. A one-sided Catalog rename keeps
owner UUID identity while recording its changed descriptor path.

One child UUID may never switch owner UUID between versions. For each UUID
that appears as a direct Catalog attribute in any input, the planner also
compares its kind and immediate owner in the complete validated identity map.
Moving that UUID into or out of a tabular section, or reusing it as a Form or
Command, fails the operation with `child_binding_changed`. Such retained
identities are not treated as attribute additions or deletions. Identities
that never appear as direct Catalog attributes remain outside this comparison.
Every observed
child's owner must exist in all three selections: omission of a Catalog is not
authority to interpret its attributes as deleted. Replacing a Catalog UUID at
the same canonical path and divergent owner path changes are rejected. To
compare a child deletion, retain its Catalog descriptor without that child.

`property_changes` compares direct Attribute elements, including `name`, as
complete structural projections. Each changed property exposes only its name,
action, and three SHA-256/size pairs; an absent property has `null` evidence.
`property_mergeability` reports `unchanged`, `same_change`, `keep_current`,
`take_upstream`, `mixed_changes`, `disjoint_changes`, or `overlap_conflict`.
Missing Attribute versions produce `not_available`. A changed child projection
with unchanged direct properties produces `unscoped_content`. Even
`disjoint_changes` is only review evidence: the row's content action remains
conservative and no XML is synthesized.

## Fingerprint boundary

`fingerprint_basis: structural_xml_json_v1` distinguishes projection hashes
from exact source hashes. A projection is canonical JSON of
`[namespace_trace_sha256, node]`; `node` recursively records its expanded XML
tag, sorted attribute name/value pairs, text, and ordered child projections
with each child's tail text. The selected element's own tail is outside it.
The sizes describe these UTF-8 canonical JSON bytes, not source XML fragments.

The namespace trace records namespace declarations, sorted at each declaring
element, with that element's one-based XML preorder index throughout the
descriptor. Its digest participates in every child/property fingerprint so a
changed prefix binding cannot disappear behind unchanged QName-valued text.
This is conservative: changing even an unused declaration, or moving its
declaration position, can change every projected property. It is not QName
resolution, schema validation or a statement of semantic equivalence.

Exact source and tree hashes retain differences outside this projection,
including declaration spelling and formatting. No XML, BSL source or property
value is returned. Names, paths and XML locations are intentional evidence.

## Bounds and verification

Defaults and ceilings are 256 files, 1 MiB per file, 16 MiB per tree and 20,000
direct child UUIDs. Limits accept positive integers only and may be lowered.
File and child limits apply to their three-version unions as well as individual
inputs. Each XML descriptor is capped at depth 64 and 100,000 elements while
parsing; each direct Attribute has at most 128 direct properties. Limits and
identity errors fail the complete operation with no partial rows.

The API reports `EDT_THREE_WAY_INVALID` or `EDT_THREE_WAY_LIMIT` with fixed
payload-free `reason` codes. Shared path/byte validation retains the existing
`THREE_WAY_INVALID` and `THREE_WAY_LIMIT` errors. Inputs are captured once and
are not mutated.

Implementation is isolated in `rentgen_core/edt_attribute_three_way.py` with a
public export. Existing Designer planner, materializer and native apply
behavior are unchanged. Tests use the selected Catalog from the existing
`packaging/fixtures/edt-inventory-v1` synthetic corpus and derived negative and
three-way cases. This does not establish compatibility with a typical
configuration, live 1C, native EDT, forms, СКД or extensions.

```powershell
py -3.11 -m pytest -q tests/unit/test_edt_attribute_three_way.py tests/unit/test_edt_inventory_fixture.py tests/unit/test_edt_inventory_metadata.py tests/unit/test_metadata_three_way.py tests/unit/test_metadata_three_way_semantics.py tests/unit/test_metadata_three_way_materialize.py tests/unit/test_metadata_three_way_bsl.py
py -3.11 -m black --check rentgen_core/edt_attribute_three_way.py tests/unit/test_edt_attribute_three_way.py
py -3.11 -m ruff check rentgen_core/edt_attribute_three_way.py tests/unit/test_edt_attribute_three_way.py
git diff --check
```
