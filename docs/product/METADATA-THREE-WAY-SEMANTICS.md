# Conservative Designer XML companion scopes

`plan_metadata_three_way(base, current, upstream)` now returns an additive
`semantics` object with `schema: 1`, `mode: "read_only"`, `coverage: "partial"`
and a deterministic `scopes` list. Existing object rows, counts, hashes,
`schema: 1`, `scope: "metadata-object-v1"` and `unsupported_files` retain their
meaning. In particular, `unsupported_files` still lists files outside the
original metadata-object view, including companions now described in `semantics`.

Each companion is bound to `(object_type, object_uuid, scope)` independently in
each input tree. The owner of `CommonModules/Item/Ext/Module.bsl` must be the
metadata object at `CommonModules/Item.xml`. A nested form requires its own
metadata descriptor: the planner never substitutes the parent catalog UUID.
Renaming the owner and moving its companion preserves this identity. Changing
the UUID at the same companion path produces `owner_identity_changed`; retaining
the companion while losing its descriptor produces `owner_binding_incomplete`
on the bound row and `owner_not_found` on an unbound row.

The planner's supported boundary is atomic comparison of the entire companion:

| Kind | Required shape | Boundary |
| --- | --- | --- |
| `bsl` | Known `Ext` module path, matching owner type, UTF-8 with optional BOM and no NUL | Entire module bytes; syntax, procedures, directives and extension annotations are unverified |
| `form` | `Ext/Form.xml`, `Form` or `CommonForm` owner, `Form` root in `http://v8.1c.ru/8.3/xcf/logform` | Entire form XML bytes; controls, IDs, event bindings and references are unverified |
| `data_composition_schema` | `Ext/Template.xml`, `Template` or `CommonTemplate` owner, direct `TemplateType=DataCompositionSchema`, schema root in `http://v8.1c.ru/8.1/data-composition-system/schema` | Entire schema XML bytes; query text, fields, settings and expressions are unverified |
| `extension` | Direct `ObjectBelonging`, `ExtendedConfigurationObject` or `ConfigurationExtensionPurpose` properties in Designer metadata | A sorted, serialized declaration group is fingerprinted; ownership against the base configuration is always `unsupported` with `extension_ownership_unverified` |

Этот план остаётся read-only и не изменяет atomic boundary companion scopes.
Отдельный [qualified materializer](METADATA-THREE-WAY.md) может собрать
in-memory candidate для доказанно раздельных прямых `Properties` самого
Designer-объекта и привязанных к владельцу BSL-модулей по узкому контракту ниже.
Формы и СКД остаются атомарными; конфликты в них, расширения и неподдержанные
оболочки блокируют весь candidate.

BSL paths currently include `Ext/Module.bsl` for common modules,
`Ext/Form/Module.bsl` for forms, `Ext/ObjectModule.bsl` and
`Ext/ManagerModule.bsl` for the explicitly enumerated metadata owner types,
`Ext/RecordSetModule.bsl` for registers, and `Ext/CommandModule.bsl` for
commands. Other BSL paths remain `scope_unsupported`; root configuration modules
and alternative export layouts are not inferred. Designer owners require the
`http://v8.1c.ru/8.3/MDClasses` object namespace. Missing owners, unknown owner
types/namespaces, unsupported encodings, wrong XML roots and missing template
type declarations each have an explicit unsupported reason.

Each scope has `action`, `status`, `reason`, owner identity, scope name, kind,
granularity, and the three paths, SHA-256 hashes and byte sizes. `action` uses
the existing `unchanged`, `same_change`, `keep_current`, `take_upstream` and
`conflict` vocabulary, including delete/modify and divergent path conflicts.
An unsupported scope still exposes byte evidence through `action`; consumers
must inspect `status` before interpreting it as supported evidence.

`status: "supported"` means that this atomic comparison has a recognized
UUID-bound scope. It does not establish a valid 1C program, form or schema.
Concurrent disjoint edits inside one module, form or schema remain
`status: "conflict"`, `reason: "atomic_overlap"`. No XML, BSL or merged tree is
returned. Extension declarations use the same atomic comparison vocabulary but
their fingerprints describe serialized declarations rather than the source
file as a whole. Extension ownership, borrowed targets and effective runtime
semantics are never certified by this plan.

The input path/byte limits run before XML inspection. Malformed XML and forbidden
DTD/ENTITY declarations fail closed; declaration scanning also covers UTF-16/32
byte layouts. Names come only from the object's direct `Properties/Name`, so
ordinary child metadata names cannot make the enclosing identity ambiguous.

## Qualified BSL materialization

`materialize_metadata_three_way` delegates a conflicting BSL companion to the
pure [BSL text primitive](BSL-THREE-WAY.md) only after the existing semantic gate
recognizes its module scope, owner type/namespace and UTF-8 bytes without NUL.
The read-only plan still reports that companion as `atomic_overlap`; the
materializer does not rewrite plan actions or claim native BSL validation.

A composite merge requires all three versions of the companion and owner,
the same owner UUID/type, exactly the same owner XML path, and exactly the same
companion path in all snapshots. Moves, missing versions and changed bindings
cannot use text merging to resolve their conflict. Unchanged scope casing may
use any already recognized spelling; casing drift still meets the existing
path validation rules.

Owner XML outside direct `Properties` must be unchanged. This includes the
existing unscoped fingerprint and, when owner bytes differ, the qualified byte
envelope around `Properties`; wrapper attributes, comments outside properties,
and properties-container attributes cannot slip past semantic fingerprints.
Direct property changes, including `Name`, retain their existing exact-selection
or qualified disjoint-property merge rules. An XML property overlap, unsupported
form/template/extension, unknown companion, or unrelated path conflict still
blocks the complete tree before any BSL primitive is invoked.

Exact `unchanged`, `same_change`, `keep_current` and `take_upstream` companion
actions retain their existing selection of original branch bytes. This includes
supported additions, deletions and one-sided moves. They do not invoke the text
primitive or normalize BOM/newlines. Owner, encoding and metadata tree limits
are still checked, including versions not selected for the candidate.

For composite BSL only, the primitive receives
`max_bytes=min(max_file_bytes, 16 * 1024 * 1024)`. A caller can lower this bound
but cannot raise the primitive's default byte, line, line-size or diff-work
limits. Its overlapping/touching edits, same-anchor insertions, BOM/newline
changes and resource-limit rejections become payload-free metadata blockers
with a `bsl_` reason prefix, for example `bsl_overlapping_edits` or
`bsl_candidate_byte_limit`. They raise `THREE_WAY_CONFLICT` with the existing
bounded `blocking_scopes` evidence. Metadata input/final-tree limit failures
continue to use `THREE_WAY_LIMIT`.

The result keeps `schema: 1` and `scope: "metadata-properties-v1"`, and returns
one complete `candidate` tree only after file/total limits, paths, UUID uniqueness
and resulting companion bindings are rechecked. It adds `merged_bsl_scopes`
hash/size/path/owner evidence, `counts.merged_bsl_scopes`, and
`merged_bsl_scopes_truncated` only when at least one BSL composite was merged;
results without a BSL composite retain their existing field set. The evidence
is limited to 256 rows without truncating the candidate. Existing
`merged_objects` counts and evidence continue to describe merged XML objects
only. A rejected module never exposes a partial
tree, BSL source text or another successfully merged scope's candidate.

This operation reads only the captured in-memory snapshots. It performs no
filesystem, 1C or EDT writes and does not run a BSL parser, compiler or native
validation command. Applying or executing its candidate remains outside this
contract.

Verification uses ordinary Python tests without starting 1C or EDT:

```powershell
python -m pytest -q tests/unit/test_metadata_three_way.py tests/unit/test_metadata_three_way_semantics.py tests/unit/test_metadata_three_way_materialize.py tests/unit/test_metadata_three_way_bsl.py tests/unit/test_bsl_three_way.py tests/unit/test_three_way.py tests/unit/test_metadata_materialize_cli.py
python -m black --check rentgen_core/metadata_three_way.py tests/unit/test_metadata_three_way_bsl.py
python -m ruff check rentgen_core/metadata_three_way.py tests/unit/test_metadata_three_way_bsl.py
python -m compileall -q rentgen_core/metadata_three_way.py tests/unit/test_metadata_three_way_bsl.py
git diff --check
```
