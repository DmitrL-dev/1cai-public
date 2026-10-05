# Experimental component status

- Scope: experimental synthetic component; no native/product claim.
- Source base: `6751cf437e79c7cbf7d9b36b10512601ffc08063` (PR66 reviewed tree).
- Reviewed semantic contract: `1701e067f1cc4a5f70ba447fe96c62c9b156845d36464d33af2cfd878c181fcb`.
- Contract after metadata-only qualification wording cleanup:
  `311476568bdb369947ee79bcec38afbbe3a20d6a94f8368f249cd5e34c9b913c`.
- Evaluated source candidate: `f28809e8ced10e9ee60e16e9552aff0d4789aa76`.
- Cargo dependency resolution/build: offline, locked, passed once.
- Development contracts/process tests: 32 + 2 passed.
- Frozen independent evaluation: 249 calls, 182 scheduled units, no missing units;
  all declared gates passed. The scoped finding/cost/coverage limits remain in
  [qualification](../../docs/product/DIAGNOSTIC-KERNEL.md).
- Runtime, protocol and dependency bytes in this source integration match that
  evaluated candidate. Documentation and public replay tests are separate additions.
- Native/1C/OS qualification, performance SLA and product acceptance: not attempted.
- Python production integration, Rust input reader, Go scanner, release targets,
  versions, packaging and release targets: unchanged. No product release is
  created by publishing this source component.

This status does not authenticate supplied evidence or establish user-facing
diagnostic readiness. Public copies of formerly hidden cases are regression
material, never a fresh held-out evaluation.
