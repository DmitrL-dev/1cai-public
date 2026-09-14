# EDT attribute evidence CLI design

## Goal

Expose the accepted read-only `plan_edt_attribute_three_way` contract through
the local CLI without pretending that caller-supplied trees are trusted
snapshots or that the result can be applied to 1C.

## Contract

Add `rentgen edt-attribute-plan` with required `--registry`, `--project`,
`--base-json`, `--current-json` and `--upstream-json` arguments. Each input is
the existing bounded metadata-tree envelope (`schema: 1`, `encoding: base64`,
`files` mapping). The command authenticates the project with
`project:read`, `source:edit` and `analysis:run` before reading any payload,
then decodes all three trees with the existing path, size, total-byte and
base64 validation. The planner receives immutable bytes and its result is
returned as one JSON envelope with the existing CLI output limit.

The command has no `--snapshot`, `--operation-id`, write, materialize, native
platform or apply option. It reports the planner's `coverage: partial` and
identity/owner failure codes through the existing redacted `CoreError` path.
Its limits are the existing metadata-tree limits plus `--max-children`,
bounded to the planner ceiling. A revoked project permission must prevent
payload reads and result emission.

## Boundaries and acceptance

The command is a transport adapter, not a second planner. It must preserve the
library result byte-for-byte after JSON normalization, reject malformed tree
envelopes and over-limit inputs, and keep live apply/materialization unchanged.
Tests cover successful evidence, malformed/base64/path/size failures, revoked
rights before payload access, owner-transfer errors, duplicate options and
CLI help. Existing metadata-materialize and full CLI regressions remain green.

## Alternatives

Embedding child rows into `metadata-plan` was rejected because that command is
snapshot/request based and would mix caller-selected byte trees with retained
source evidence. A new MCP surface was deferred until the CLI contract is
qualified; the local CLI is the smallest reviewable transport boundary.
