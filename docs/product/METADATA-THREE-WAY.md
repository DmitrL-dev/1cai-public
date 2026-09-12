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
do not expose a supported UUID are listed in `unsupported_files`; callers must
run the path planner or a type-specific adapter for them. The result has
`coverage="partial"` until property-level merge, UUID ownership across extensions,
BSL edits and native test/rollback are all qualified.

```python
from rentgen_core.metadata_three_way import plan_metadata_three_way

plan = plan_metadata_three_way(base_files, current_files, upstream_files)
```

Input paths and byte limits are the same bounded limits as
`plan_three_way()`. Duplicate identities, malformed metadata UUIDs, unsafe
paths, collisions and oversized trees fail closed. This is the first semantic
layer for configuration updates. DTD and ENTITY declarations are rejected
before parsing; it is not a live apply authority.
