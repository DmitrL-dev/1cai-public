# UUID-aware metadata updates

`rentgen_core.metadata_three_way.plan_metadata_three_way()` extends the
path-bytes update dry-run with a conservative Designer XML object view. For
recognized `MetaDataObject` files it identifies an object by `(type, UUID)` and
reports its path, name and byte digest in base/current/upstream. Renames and
file moves therefore remain attached to the same object identity; divergent
content or moves become `conflict`.

For objects that contain one unambiguous `Properties` element, the result also
contains `property_changes`. Each changed direct property is represented by its
name, action, hash and size; the value itself is never returned. The enclosing
`property_mergeability` is `same_change`, `keep_current`, `take_upstream`,
`disjoint_changes`, `overlap_conflict`, `path_only`, `unscoped_content` or
`unchanged`. This is
evidence for review: `disjoint_changes` shows that current and upstream touched
different properties, but the planner still leaves the object action
conservative and does not synthesize XML. Objects with missing or ambiguous
properties use `not_available`.

The planner emits only hashes, sizes and names. It never writes a tree, resolves
a conflict automatically or invokes 1С/EDT. BSL, forms, СКД and XML files that
do not expose a supported UUID remain listed in `unsupported_files`, which
describes files outside the original object view. Recognized companions also
have UUID-bound `semantics` rows under the
[companion scope contract](METADATA-THREE-WAY-SEMANTICS.md). The planner keeps
these scopes atomic, including BSL modules that the materializer can qualify
for a composite merge. The result has
`coverage="partial"` until property-level merge beyond the qualified boundary
below, UUID ownership across extensions,
BSL semantics beyond the qualified text boundary and native test/rollback are
all qualified.

```python
from rentgen_core.metadata_three_way import plan_metadata_three_way

plan = plan_metadata_three_way(base_files, current_files, upstream_files)
```

Input paths and byte limits are the same bounded limits as
`plan_three_way()`. Duplicate identities, malformed metadata UUIDs, unsafe
paths, collisions and oversized trees fail closed. This is the first semantic
layer for configuration updates. DTD and ENTITY declarations are rejected
before parsing; it is not a live apply authority.

## Qualified in-memory property and BSL candidate

`rentgen_core.materialize_metadata_three_way(base, current, upstream)` builds a
`dict[str, bytes]` candidate in memory. The planner and materializer capture each
input mapping once and use those validated snapshots for all hashes, UUID
bindings, planning and byte selection. Neither function writes files or invokes
1C/EDT.

An object conflict is resolved only when `property_mergeability` is
`disjoint_changes`, its unscoped content is unchanged, its UUID-bound path action
is not a conflict, and every direct Designer `Properties` element is
unambiguous. `keep_current`, `same_change` and `unchanged` properties select the
current element; `take_upstream` selects the upstream element. A missing selected
element means deletion. Property additions retain the relative order of both
branches; incompatible orders fail closed. A supported move selects the same
object's destination path and removes its superseded paths.

This first semantic materializer qualifies UTF-8 XML (with optional BOM), the
Designer metadata namespace, and an identical byte envelope outside the direct
property elements. It copies complete property byte fragments, preserving
namespace declarations, prefixes, QName values and nested property XML. It does
not reserialize the enclosing object. Non-whitespace content between properties,
changes hidden by XML fingerprints (including comments), changed namespace
contexts or wrapper attributes, ambiguous/missing properties and unsupported
encodings fail closed for semantic merging. Selected property fragments retain
their trailing whitespace. This is conservative qualification, not full Designer schema or
native round-trip validation.

Other non-conflicting objects and ordinary paths retain atomic byte selection,
including additions and deletions. Recognized BSL companions may additionally
use the [qualified BSL composite contract](METADATA-THREE-WAY-SEMANTICS.md#qualified-bsl-materialization):
all three versions must have the same owner UUID/type, owner XML path and
companion path, with owner XML outside direct `Properties` unchanged. Direct
properties retain the existing XML merge rules; all other blockers still apply.
Exact BSL actions select original branch bytes. Forms and СКД companions remain
atomic, and conflicting or unsupported scopes block the complete candidate.
The candidate's owner bindings are checked again after selection.
Companion suffixes and `Ext` segments are
matched without case sensitivity, and owner lookup uses canonical path identity.
Evidence retains the original paths and scope spelling. Orphan `Ext/Form.xml`
and `Ext/Template.xml` scopes are rejected in every casing, including at the tree
root. An unsupported scope blocks the entire result
even when its bytes are unchanged. Extension declarations remain unsupported;
unscoped XML changes are never semantically merged. Replacing an object's UUID
at a reused path also blocks materialization.

The returned result has `schema: 1`, `scope: "metadata-properties-v1"`,
`status: "ready"`, the three input digests, `candidate_digest`, and `candidate`.
`counts` reports input objects, semantically merged objects, candidate files and
the original path actions (which may include conflicts resolved by the qualified
property or BSL merge). `merged_objects` describes merged XML objects only and
provides at most 256 UUID/path/hash/size
evidence rows; `merged_objects_truncated` indicates omitted rows. Candidate
paths and file/total-byte limits are validated again before returning. When a
BSL composite is merged, the result also includes `merged_bsl_scopes`,
`counts.merged_bsl_scopes` and `merged_bsl_scopes_truncated` as specified by the
companion scope contract.

Any unresolved or unsupported scope raises `CoreError` before exposing a partial
candidate. Conflict details contain at most 256 `blocking_scopes`, the full
`blocking_scope_count`, and `scopes_truncated: true` when needed. Reasons use
fixed identifiers; error details contain no XML or BSL payload.

```python
from rentgen_core import materialize_metadata_three_way

result = materialize_metadata_three_way(base_files, current_files, upstream_files)
candidate_files = result["candidate"]
```

The ready status establishes only this in-memory merge boundary; native apply,
extension ownership and runtime correctness still require their own validation.
