# EDT identity three-way planner

## Problem

`rentgen edt-inventory` now exposes a bounded, snapshot-bound identity
inventory, but an update review still has to compare three inventories by hand.
The existing `edt-attribute` planner is deliberately Catalog/Attribute-specific
and returns property evidence. The next slice needs a general identity plan
without pretending that XML, forms, СКД, extensions, or native platform
semantics are mergeable.

## Goal and non-goals

The new pure function `plan_edt_identity_three_way(base, current, upstream)`
will compare three already-produced inventory envelopes. It will return a
deterministic read-only plan keyed by `(layer_id, canonical_uuid)` and preserve
only identity, owner, layer, path and hash evidence. It will never read a
filesystem, invoke EDT/1C, create XML, materialize a candidate, or write a
configuration.

This slice covers rows present in the accepted `edt_metadata_inventory`
contract, including root objects and validated direct child identities. It does
not add new parsers, infer extension ownership, merge properties, qualify form
or СКД behavior, or assert compatibility with `.cf/.cfe` files or a typical
configuration.

## Input contract

Each input is the current `edt-inventory.result` producer object with
`parser: edt_identity_v1`, `coverage: partial`, `identity_scope: snapshot_layer`,
`owner_basis: direct_xml_containment_only`, `layer_basis:
pinned_snapshot_declaration`, and an `objects` list. There is no input `schema`
field: the parser profile is the versioned identity contract. Every object must
contain the existing inventory identity fields `canonical_uuid`,
`observed_uuid`, `type`, `name`, `xml_path`, `owner`, `layer`, and `source_ref`.
`source_ref.raw_sha256` is required; the current producer does not expose a
source byte size, so the planner records `source_size_bytes: null` rather than
inventing one. UUIDs and hashes are canonicalized and validated.

The planner validates all three envelopes before producing any row. It rejects
unknown or duplicate identity records, malformed UUIDs, missing owner/layer
evidence, project-id mismatches, malformed snapshot references, changed source
references that cannot be explained by the selected version, and non-partial
or fabricated coverage claims. Base, current and upstream normally have
different snapshot IDs; those IDs are recorded per version and are not required
to match. A missing root/object in one envelope is not
interpreted as a deletion unless the corresponding retained owner evidence is
present in that envelope; otherwise the result is `unsupported` with a stable
reason rather than an inferred delete.

All inputs are captured into normalized immutable mappings once. Limits cover
each envelope and the three-version union: maximum serialized input bytes,
objects, owners, layers and result rows. Limits are positive integers and may
only be lowered from fixed ceilings. No input value or mapping is reread after
normalization.

## Comparison semantics

The identity key is `(layer.layer_id, canonical_uuid)`. For every key in the
three-way union, the planner compares a canonical identity projection
containing type, name, owner UUID/path, layer declaration, XML path and source
hash/size. Actions follow the existing deterministic vocabulary:

* `unchanged` — current equals both base and upstream;
* `same_change` — current and upstream make the same change from base;
* `keep_current` — only current changed;
* `take_upstream` — only upstream changed;
* `conflict` — both changed differently, or one deletes while the other
  modifies;
* `unsupported` — the evidence cannot prove a safe identity comparison.

An identity moving between layers, changing type, changing owner UUID, or
appearing under divergent owner paths is always `unsupported` with a stable
reason. A UUID reused for a different identity is never treated as an addition.
An addition or deletion is reported only when the retained owner/layer evidence
is complete for that version. Rows are sorted by layer ordinal, layer ID and
canonical UUID; reason codes and counts are deterministic.

The result contains `schema: 1`, `scope: edt-identity-v1`, `mode: read_only`,
`coverage: partial`, exact input envelope digests, bounded counts and
`objects`. Each row exposes the key, action, reason (when applicable), and
version records without XML/property payload. The result explicitly states
`materialization: unavailable` and `native_validation: unavailable`.

## CLI transport

Add `rentgen edt-inventory-plan` as a separate read-only command. It requires
`--registry`, `--project`, `--base-json`, `--current-json` and
`--upstream-json`; each file is a UTF-8 inventory object copied unchanged from
the `result` field of `edt-inventory` (it has `parser: edt_identity_v1` and is
not the metadata-tree/base64 envelope). The command does not resolve a
snapshot and has no `--apply`,
`--output`, `--workspace`, `--operation-id`, native profile or caller-supplied
source-root option.

The transport authenticates `project:read` before each file read, before the
planner result is serialized, and before emitting an error. Planner diagnostics
are replaced with stable payload-free CLI messages; revocation suppresses
stale results. Input and output envelopes have fixed byte ceilings, and an
oversized result fails with `OUTPUT_LIMIT_EXCEEDED` without partial output.

## Architecture and compatibility

The planner lives in a new `rentgen_core/edt_identity_three_way.py` module and
is exported from the package. It may reuse only pure normalization and action
helpers from the existing three-way modules. `edt_inventory.py`, the snapshot
resolver, metadata readers, writers, native gates and existing commands retain
their current behavior. The CLI adapter is separate from `edt-inventory` so a
future native materializer can consume a reviewed plan through an explicit
contract rather than gaining write access accidentally.

## Verification

Tests will cover valid unchanged/same/one-sided/conflict cases, additions and
deletions with retained owners, rename evidence, layer/type/owner moves,
duplicates, malformed envelopes, snapshot/project/source binding, limits,
mapping drift, payload redaction, revocation before/during/after reads and
serialization, output caps, unsupported options, and regression of all existing
CLI commands. Static checks and isolated sdist byte/content checks will include
the new module, contract document and tests. The accepted candidate will require
the full local suite, the independent Astra xhigh review of the full release
diff, and the exact Windows Product CI run before it is considered accepted.

## Explicit boundary

This planner is review evidence only. It does not make the product “ready” for
live updates, does not replace the 1C Configurator, and does not close the
remaining native writer/undo, typical-configuration matrix, autonomous audit,
business-metric producer, Spectorn route or pilot/cutover gaps.
