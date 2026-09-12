# UUID-aware metadata updates

`rentgen_core.metadata_three_way.plan_metadata_three_way()` extends the
path-bytes update dry-run with a conservative Designer XML object view. For
recognized `MetaDataObject` files it identifies an object by `(type, UUID)` and
reports its path, name and byte digest in base/current/upstream. Renames and
file moves therefore remain attached to the same object identity; divergent
content or moves become `conflict`.

The planner emits only hashes, sizes and names. It never writes a tree, resolves
a conflict automatically or invokes 1С/EDT. BSL, forms, СКД and XML files that
do not expose a supported UUID are listed in `unsupported_files`; callers must
run the path planner or a type-specific adapter for them. The result has
`coverage="partial"` until object properties, UUID ownership across extensions,
BSL edits and native test/rollback are all qualified.

```python
from rentgen_core.metadata_three_way import plan_metadata_three_way

plan = plan_metadata_three_way(base_files, current_files, upstream_files)
```

Input paths and byte limits are the same bounded limits as
`plan_three_way()`. Duplicate identities, malformed metadata UUIDs, unsafe
paths, collisions and oversized trees fail closed. This is the first semantic
layer for configuration updates; it is not a live apply authority.
