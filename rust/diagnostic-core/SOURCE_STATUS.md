# Experimental component status

## Historical synthetic-profile qualification

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
- At the original synthetic-profile integration, runtime, protocol and dependency
  bytes matched that evaluated candidate. Documentation and public replay tests
  were separate additions. Later source-fact additions have separate build bytes
  and do not inherit that qualification.
- Native/1C/OS qualification, performance SLA and product acceptance: not attempted.
- The original synthetic-profile integration did not change Python production
  integration, Rust input reader, Go scanner, versions, packaging or release
  targets. That historical statement does not describe later source-fact work.

This status does not authenticate supplied evidence or establish user-facing
diagnostic readiness. Public copies of formerly hidden cases are regression
material, never a fresh held-out evaluation.

## Separate source-fact candidate: acceptance pending

The current tree additionally contains the pure
`rentgen_diagnostic_core::source_facts::evaluate(&[u8])` entry point and
`rentgen-source-facts` Linux executable. The original synthetic entry point and
wire semantics remain separate. Linux libc ownership bootstrap and newly linked
executables require their own build hashes; the historical executable hash is
not a hash of this candidate.

The Python `source-facts` owner connects immutable input-core ZIP bytes, a
separate Go lexical observer and the Rust source-only envelope. It may disclose
only a lexical selector, candidate header Export marker and candidate XML Server
property. Receiver binding and runtime relation always remain unknown. XML is
the restricted handwritten profile, not Designer/native qualification.

The source-fact protocol is frozen at SHA-256
`ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.
[CLI usage and delivery limits](../../docs/product/SOURCE-FACTS.md) and the
[full contract](../../docs/product/SOURCE-FACTS-PROTOCOL.md) describe this path.
Its development contracts, owned-process lifecycle checks and independent
handwritten-source qualification are separate gates. Final acceptance is pending;
no unseen/unrun suite is counted as passed. No native 1C, AI utility, speedup,
Windows/macOS source-fact delivery or full-product readiness is claimed.

The next Core source package includes both crates and their documentation. This
packaging change does not replace the fixed earlier Core `25743f7` / Companion
`a4d8504` release targets or their prepared assets, and creates no release itself.
