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

The supported boundary is atomic comparison of the entire companion, not
semantic merging inside it:

| Kind | Required shape | Boundary |
| --- | --- | --- |
| `bsl` | Known `Ext` module path, matching owner type, UTF-8 with optional BOM and no NUL | Entire module bytes; syntax, procedures, directives and extension annotations are unverified |
| `form` | `Ext/Form.xml`, `Form` or `CommonForm` owner, `Form` root in `http://v8.1c.ru/8.3/xcf/logform` | Entire form XML bytes; controls, IDs, event bindings and references are unverified |
| `data_composition_schema` | `Ext/Template.xml`, `Template` or `CommonTemplate` owner, direct `TemplateType=DataCompositionSchema`, schema root in `http://v8.1c.ru/8.1/data-composition-system/schema` | Entire schema XML bytes; query text, fields, settings and expressions are unverified |
| `extension` | Direct `ObjectBelonging`, `ExtendedConfigurationObject` or `ConfigurationExtensionPurpose` properties in Designer metadata | A sorted, serialized declaration group is fingerprinted; ownership against the base configuration is always `unsupported` with `extension_ownership_unverified` |

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

Verification uses ordinary Python tests without starting 1C or EDT:

```powershell
python -m pytest -q tests/unit/test_metadata_three_way.py tests/unit/test_metadata_three_way_semantics.py
python -m black --check rentgen_core/metadata_three_way.py tests/unit/test_metadata_three_way_semantics.py
python -m ruff check rentgen_core/metadata_three_way.py tests/unit/test_metadata_three_way_semantics.py
git diff --check
```
