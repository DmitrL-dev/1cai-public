# Experimental diagnostic and source-fact core

A small experimental Rust component implementing the reviewed bounded
[protocol](PROTOCOL.md). It evaluates typed evidence and selects an advisory next
check. It never executes that check, authenticates provenance, grants permission,
reads a project/database, runs a process, calls a model or changes a product.

The synthetic entry point remains separate from the product CLI/MCP. A second,
incompatible source-fact profile is now present in the candidate source tree;
its Linux process adapter is called by the experimental Python `source-facts`
command after immutable ZIP acceptance and Go lexical scanning. This candidate
has not completed its source-fact acceptance gates. Core `25743f7` and Companion
`a4d8504` remain the fixed earlier release targets.

## Source layout

- `src/parse.rs`: strict 64 KiB JSON admission, schema and relation validation.
- `src/model.rs`: closed typed protocol and result records.
- `src/engine.rs`: evidence withdrawal/replacement, conflicts, current inference,
  bounded compatible-outcome projection and deterministic selection.
- `src/catalog.rs`: five bounded hypotheses across three target kinds and six
  fixed checks. Hypotheses may coexist; there are no probabilities or one-hot causes.
- `src/main.rs`: one bounded synthetic JSON request on stdin, one result on stdout.
  Protocol errors are generic and stderr remains empty. It has no configuration,
  native adapter, filesystem/network/probe access or executable check payload.
- `src/source_facts/`: strict, pure source-only envelope evaluation. This profile
  accepts host assertions about three observations, never binding/runtime proof.
- `src/bin/rentgen-source-facts.rs`: Linux-owned one-shot framed transport for
  the source-only profile, with parent-death checks before its hello message.
- `tests/`: development contracts, process-boundary examples and public replay
  of previously observed synthetic wire cases. Public replay is regression,
  not a new independent held-out evaluation.

The pure entry point is `rentgen_diagnostic_core::evaluate(&[u8])`. The schema
accepts synthetic profile labels only. Strings claiming attestation or access
cannot become authenticated provenance: every result explicitly reports
`experimental_synthetic_not_authenticated`. A real host must independently verify
receipts, keep cumulative budgets, enforce cancellation/deadlines and recheck
permissions before fact capture, before check execution and before disclosure.

## Frozen boundary and verification status

Contract SHA-256:
`311476568bdb369947ee79bcec38afbbe3a20d6a94f8368f249cd5e34c9b913c`.
The final two wording changes clarify component qualification only; rule/schema
semantics are identical to the independently reviewed contract. Independent
fixtures, numerical criteria and implementation were frozen before evaluation.
The initial implementation author did not inspect the held-out cases beforehand.

The first offline locked build passed 32 contract and two stdio tests. The separate
frozen synthetic evaluation made 249 calls with no false diagnoses, unjustified
refutations, protocol-conformance failures or canary leaks. Each 24-case split
produced a bounded finding in 12/12 support cases and no diagnosis in 12/12 controls.
The adaptive selector used 13 requests versus 15 for the fixed order in each
eight-trial split, with **equal cost and disclosure: 21 units**. This is fewer
requests, not lower information cost or measured native speedup. Held-out finding
recall was 14/15; the separate budget-solvable two-conflict case remained 0/1.

These are owned symbolic evidence histories under five known rules, not unseen
source-code or real 1C diagnostics. Full scope and provenance:
[component qualification](../../docs/product/DIAGNOSTIC-KERNEL.md).

For an authorized offline development check using a prepared pinned Rust 1.92.0
and the reviewed vendor cache, the crate-local command is:

```sh
cargo test --offline --locked -j 1 -- --test-threads=1
```

The coordinating host applies explicit wall/CPU/memory limits and keeps the
build target separate from concurrent research. Do not infer native platform
qualification from a successful Linux synthetic run. The strict stdin adapter is
intended only for the synthetic harness; its result is not a user-facing diagnosis.

## Separate source-fact candidate

Build and CLI usage: [SOURCE-FACTS.md](../../docs/product/SOURCE-FACTS.md).

The exact source contract is [submitted source facts v1](../../docs/product/SOURCE-FACTS-PROTOCOL.md),
SHA-256 `ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.
The pure entry point is `rentgen_diagnostic_core::source_facts::evaluate(&[u8])`.
The original `evaluate` entry point and synthetic protocol stay unchanged.

The new profile records a lexical selector, a candidate routine's Export marker,
and a restricted XML Server property. Its receiver binding and runtime relation
always remain unknown. Direct library/stdio assertions are not authenticated
source evidence; the Python owner separately verifies image/input hashes, source
receipts, current project permissions and child termination before disclosure.

The XML profile is explicitly handwritten and restrictive. It does not certify
Designer exports, configuration completeness, namespace resolution or real 1C
execution. No native probe, database call, model or suggested check is executed.
Windows/macOS delivery of the new host workflow is not qualified.

Development contracts, ancillary fault-injected lifecycle checks and the
independent handwritten source cohort are separate gates. The synthetic results
above do not qualify this new profile; final source-fact acceptance is pending.

## Important coverage limits

Call context covers only statically bound common-module calls, including a
separately witnessed server bridge. Forms and dynamic routes abstain. Receiver
shape requires the retained immediate receiver and its exact schema/key/metadata
witness; values, query rows, exception text and getters are outside the protocol.
Source/runtime mismatch requires the attested type/member correlation; ZIP UUIDs
are unverified. It does not assign old-session/extension/export-source causes.

The selector uses one-step status projections, preserves known values, and gives
both policies the same eligible/useful list. The harness may choose the smallest
check ID from that list for fixed-order comparison. Bundled flags disclose three
facts and cost three units; a copy-presence check discloses one and costs one.
Three attempted adapter responses is a separate bound. A request awaiting consent
is not an attempt and carries no observation/cost charge.

Some repair chains need more than one otherwise non-resolving check and therefore
abstain. Mismatch beginning with only a retained-receiver anchor needs four checks
to support its finding, beyond the three-response budget. These are intentional
limits, not evidence that an unsupported explanation is false.

## Dependencies

Pinned serde `1.0.228` and serde_json `1.0.149` remain the portable dependencies.
Linux additionally uses libc `0.2.186` only for the source adapter's ownership
bootstrap. All twelve registry package versions are reused from the reviewed
input-core lock; no service or model is introduced.
See [dependency provenance](DEPENDENCY_PROVENANCE.json) and
[third-party notices](THIRD_PARTY_NOTICES.md), including the full copied notices.
The first offline `--locked` Cargo invocation passed. Dedicated CI repeats the
Rust contracts on Linux and Windows; this does not qualify real 1C adapters,
macOS or the complete product on either OS.
