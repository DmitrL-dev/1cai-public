# Synthetic EDT identity inventory corpus

`provenance: synthetic`; `scope: read_only_contract`.

This corpus was authored for Python reader tests. No file was exported or
validated by EDT or 1C. `native_execution`, `live_acceptance` and
`cf_cfe_acceptance` are all false in the manifest. There is no user
configuration data and no claim of platform compatibility.

`base/` contains nine minimal MDO descriptors with 17 expected identities:
nine roots, seven direct embedded declaration kinds, and one nested tabular
section attribute. They omit properties required by a real platform project.
The five additional assets are deliberately opaque text placeholders. In
particular, `configuration.cf` and `extension.cfe` are **not 1C containers**;
`.form` and the schema XML are not valid XML, and BSL is not a program. Their
purpose is to prove that the identity inventory counts paths without opening
or certifying asset bytes.

`negative/` contains six separate inputs: malformed XML, a foreign namespace,
an invalid UUID, a missing name, an unknown identity-bearing extension shape,
and a forbidden DTD. The extension example is deliberately unsupported; it is
not a statement about an accepted EDT extension serialization. Each negative
file is presented at its manifest `source_path` in a fresh snapshot context.

`manifest.json` fixes each input's SHA256/size, expected error codes, the base
layer declaration, and independent UUID/name/type/XML-path/owner expectations.
Tests do not derive these expectations from the production parser or its type
dictionary. SHA256 here detects fixture drift; it is not runtime attestation.
The tests verify the complete file list, compare identities and SourceRefs,
reject unsupported cases without partial results, and enforce opaque no-read
behavior. Layer and additional boundary cases use explicit synthetic inputs
in the same test file.

Run from the repository root:

```powershell
py -3.11 -m pytest -q tests/unit/test_edt_inventory_fixture.py
```

See [the compatibility matrix](../../../docs/product/CONFIGURATION-COMPATIBILITY.md)
for distinctions between this contract, other readers, Designer comparison,
and the separately recorded historical native experiments.
