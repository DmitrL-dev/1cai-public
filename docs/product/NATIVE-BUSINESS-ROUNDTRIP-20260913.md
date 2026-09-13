# Native catalog business roundtrip — 2026-09-13

The installed Windows 1C 8.3.27.2342 full client performed a fresh, bounded
write/read/rename/update/delete scenario against an owned synthetic `Products`
catalog. All 19 native processes exited with code 0. Ten of these were separate
`ENTERPRISE` launches, including the permissions preflight. Existing exclusive
EDT and migration outputs were not rerun or modified.

The [sanitized evidence](evidence/native-business-roundtrip-8.3.27.2342-20260913.json)
records process outcomes, normalized command lines, runtime observations,
metadata identities, source and result sizes/SHA-256, and the retained failed
setup attempt. This is host-observed, unattested evidence for one synthetic
scenario. It does not qualify arbitrary `.cf`/`.cfe` files or the product's
metadata apply/undo workflow.

## Observed behavior

Each row below ran in a new full-client process, which closed before the next
operation. A managed application startup handler called the server test module,
wrote its JSON result, and exited the application. Runtime exceptions were
reported as `status=failed`; native process exit 0 alone was never treated as
proof of a passing business assertion.

| Operation | Observed result |
| --- | --- |
| Rights preflight | Read, Insert, Update and Delete were all available in the new owned base |
| Read before creation | Expected `RECORD_NOT_FOUND` failure |
| Create item through `Article` | `Артикул-исходный-001` written; catalog count 1 |
| Reopen and read `Article` | Exact original value and record reference |
| Load/update/check renamed fixture, reopen and read `SKU` | Exact original value and reference survived `Article` → `SKU` |
| Update item through `SKU` | `SKU-обновлённый-002` written to the same record |
| Reopen and read `SKU` | Exact updated value and reference |
| Read old `Article` field | Expected native `Поле объекта не обнаружено (Article)` failure |
| Delete the test item | Physical `CatalogObject.Delete()` completed; catalog count 0 |
| Reopen after deletion | Expected `RECORD_NOT_FOUND` failure |

The scenario uses standard catalog object creation, `Write()`, `GetObject()` and
deletion. These operations are described in the official
[1C catalog reference](https://kb.1ci.com/1C_Enterprise_Platform/Tutorials/Practical_developer_guide_8.3/Quick_developer_reference/Catalogs/1C_Enterprise_language_objects_used_for_operations_with_catalogs/?language=en).
The observation above comes from the actual host run, rather than from that
documentation or a mocked catalog.

## Metadata and input identity

All 13 XML files in `packaging/fixtures/edt-metadata-v1/{baseline,created,renamed}`
matched the checked-in manifest before execution; their hashes were checked
again after the run. The owned copies received only the test common module and
managed application startup handler, with a corresponding common-module entry
in `Configuration.xml`. The checked-in fixture was unchanged.

Native XML dumps of both schemas verified these identities:

| Object | Preserved UUID or binding |
| --- | --- |
| Configuration | `c5bbdafc-ac33-454e-98bb-5492e6f90b3d` |
| Catalog `Products` | `fb28b18e-d2a3-4f48-8390-c0d609c9e7c0` |
| Attribute `Article` / `SKU` | `eb298009-8fc5-4a2f-8812-902daeed99df` |
| Form `ItemForm` | `44821c5c-7eaf-4b40-ba04-dc79e0c71268` |
| Form field | Element name `Article`, ID 7; main attribute `Объект`, ID 1 |
| Form data path | `Объект.Article` → `Объект.SKU`, string length 32 |
| Test common module | `07df268b-8978-434a-b345-d24cf08f4eb9` |

The native dumps also preserved the normalized BSL of both test modules.
The complete record reference matched throughout creation, migration, update,
readback and deletion. Its public representation is SHA-256-redacted; raw values
remain only in the ignored local proof.

## Commands, limits and closure

The executed host command from the checkout root was:

```powershell
python output/native_business_roundtrip_20260913.py
```

The helper creates a fresh UUID output each time and refuses an existing output.
The successful output was
`output/native-business-roundtrip-7b6f0621-3fe6-4787-b9dd-e0bab5b20fab`.
Its `steps.json` retains exact absolute argument arrays and native command lines.
The public evidence substitutes `<worktree>` for the host checkout path.

Both schema stages ran `/LoadConfigFromFiles`, `/CheckConfig` with Server,
ExternalConnection, ThinClient and ThickClientManagedApplication contexts,
`/UpdateDBCfg`, and `/DumpConfigToFiles`. Actual behavior used `ENTERPRISE /F`
and `/C` with a fixed operation, field, synthetic value and result path. No
external connection registration or YAxUnit extension was changed.

Execution was bounded to 600 seconds total, 120 seconds per native process,
1 GiB of owned output, at least 1 GiB free space, 10,000 output entries,
128 KiB per native log and less than 64 KiB per runtime result. Source files and
the full-client executable were held by the existing retained-input pinning
mechanism. Native children belonged to the existing Windows owned-job wrapper.

The executable was 1,815,632 bytes, with SHA-256
`2a9ef3653367b6de29000a3a51749a19e6450134347925713c9075674e9f0956`.
After every invocation, the owned job reported zero active descendants. An
independent process query after completion found no native process for the
successful run. A read-only `FileStream` opened `1Cv8.1CD` with `FileShare.None`
and closed successfully. The closed database was 3,416,064 bytes, SHA-256
`c234cffc261849eed5deb4f3df640150620510c1402fcea4bee6e29890608a2b`.
The base and proof files were retained; only the owned test record was deleted.

## Verification and retained setup failure

The helper acceptance logic was written after 10 tests first failed because
the helper did not yet exist. Its nine negative cases reject lost migration
values, stale SKU values, changed record references, false missing-data claims,
unrelated native errors, failed cleanup, nonzero process exits and active
descendants.

```powershell
python -m pytest -q output/test_native_business_roundtrip_20260913.py tests/unit/test_edt_metadata_fixture.py tests/unit/test_metadata_migration_fixture.py
```

Result: 17 passed, exit 0. The first new native attempt,
`output/native-business-roundtrip-365db3ce-d070-4119-a345-443d495c61e8`,
stopped at `/CheckConfig`, exit 101: the helper used the reserved BSL keyword
`Выполнить` as a function name. Renaming it to `ПроверитьОперацию` fixed that
specific compiler error. Its three native steps and zero-descendant closure
receipt remain separate from the successful run. The failed base was never
used for the business scenario.

The ignored scripts, raw proof and focused-test logs are host-only artifacts;
they are not shipped in the product package. Public evidence contains their
sizes and hashes. Existing production Python APIs, fixture inputs and package
configuration were unchanged by this qualification.

## Remaining scope

This confirms synthetic catalog persistence and cleanup on one installed
platform. Managed-form bindings were inspected in native XML; the form was not
opened interactively. No arbitrary customer configuration, full binary
`.cf`/`.cfe` roundtrip, live EDT writer, product apply/undo transaction, role
matrix, concurrent user scenario, production metrics source or business-data
freshness pipeline was exercised. Dependent platform DLLs were not fully
pinned. The earlier [metadata migration proof](evidence/metadata-migration-v1.json)
remains separate evidence for its YAxUnit value cases and wrong-UUID rejection.
