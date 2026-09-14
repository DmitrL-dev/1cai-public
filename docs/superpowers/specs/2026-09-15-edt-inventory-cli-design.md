# EDT Identity Inventory CLI Design

## Goal

Expose the accepted `rentgen_core.edt_inventory.edt_metadata_inventory` reader
through the local CLI so a developer or owner can obtain bounded UUID, owner,
layer and SourceRef evidence from one explicitly selected published snapshot.
The command remains read-only and never reads the live checkout, writes a
candidate, starts 1C/EDT, or changes metadata.

## Contract

The command is `rentgen edt-inventory` and requires `--registry`, `--project`
and `--snapshot`. It accepts an optional `--layer-id`. The limits are explicit
integer options for the existing `EDTInventoryLimits` fields:
`max-xml-bytes`, `max-nodes`, `max-depth`, `max-inventory`, `max-collection`,
`max-total-bytes`, `max-asset-bytes`, `max-mdo-files` and `max-identities`.
Defaults and ceilings are the library defaults and maxima; callers may lower
them but cannot raise them. The transport has a bounded UTF-8 JSON output cap
and fails before emitting a partial inventory when the cap is exceeded.

The command authenticates the Windows principal and requires `project:read`
before snapshot resolution and before each source read performed by the shared
snapshot session. It rechecks that permission after result serialization and
when emitting an error. A revoked request therefore emits only the fixed
authorization error and never stale source paths or identity diagnostics.

The result is the unchanged library inventory wrapped in the existing
`{"result": ..., "request_id": ...}` envelope. It retains `coverage: partial`,
`parser: edt_identity_v1`, layer rows, identity rows and verified SourceRefs.
Library errors keep their stable code but the CLI replaces arbitrary messages
and details with a payload-free fixed message. The command has no
`--operation-id`, `--output`, `--workspace`, `--apply` or native options.

## Architecture and alternatives

The recommended approach is a dedicated transport adapter in `cli.py`. It
constructs typed `EDTInventoryLimits`, resolves the selected snapshot through
the existing `ContextResolver`, calls the existing library function once and
returns `_ProposalCommandResult` so the common output-limit and reauthorization
path is reused. This keeps the library contract and existing metadata commands
unchanged.

Extending `metadata-summary` would mix Designer and EDT identities and make
its partial coverage ambiguous. Adding MCP first would duplicate the local
authorization and snapshot-binding surface before the CLI contract is usable.
Both alternatives are deferred.

## Failure and safety rules

- No snapshot is resolved until limits and `project:read` are validated.
- A missing or foreign snapshot, layer, malformed EDT document, identity
  collision, source tamper or revoked membership fails the whole request.
- The inventory reader's existing no-partial-result behavior is preserved.
- Output size is checked after canonical serialization and before stdout; an
  oversized result returns `OUTPUT_LIMIT_EXCEEDED` without identity rows.
- No path supplied by the caller is opened; all source bytes come from the
  selected retained snapshot.

## Verification

Tests cover parser/help and repeated or unsupported options, limit validation
before snapshot access, exact library invocation, snapshot/layer binding,
authorization revocation during resolution and source reads, payload-free
errors, output limits and regression of existing metadata CLI commands. Static
checks, the full Python suite and isolated sdist checks must pass. The command
is documented in `docs/product/EDT-INVENTORY-IDENTITY.md`, linked from the
README, and included in the package documentation allowlist.

## Non-goals

This change does not parse non-MDO assets, infer extension adoption, merge
layers, materialize XML, write a source tree, execute 1C/EDT, add a watcher or
connect Spectorn.
