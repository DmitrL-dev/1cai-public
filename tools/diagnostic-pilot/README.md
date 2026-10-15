# Diagnostic policy pilot

Research-only comparison harness for the finite typed evidence protocol in
`rust/diagnostic-core`. It is separate from the shipped CLI, GUI and Companion.
The deterministic policies and real Rust process can run without model packages.
The optional ready-agent adapter runs the actual LangChain `create_agent` tool
loop with a local Ollama model; hybrid supplies the same agent with Rust advice.

This is implementation of the comparison framework, **not acceptance of an AI
diagnostician, native 1C execution, an independently authored holdout, or an
architecture winner**. Every generated report retains those three acceptance
flags as `false`. Missing dependencies/model produce `inconclusive`, never a
skipped success. A small-model smoke proves only the exercised runtime path.

## Evidence and admission

- The host owns the case outcomes, capabilities, consent and budget. A policy
  receives only the current typed envelope and the independently admissible
  checks. Case labels, provenance, expected findings, future outcomes and pair
  labels are withheld from this view.
- Check admission uses the closed catalog, prerequisites, current scope,
  capability, consent, prior attempts and remaining budget. It does not use the
  Rust candidate list, expected information gain or a `no_status_change` filter.
  The two-conflicting-premise control permits a useful first check even when it
  cannot immediately change a hypothesis state.
- An attempt is charged once, including timeout/unavailable. A timeout discloses
  no negative fact. The three-value call-flags result is atomic. Missing consent,
  incompatible evidence, wrong receiver shape and invalid bundles commit nothing.
- Scope includes case/snapshot/revision/session/context/platform/compatibility/
  execution. `advance_scope` is a trusted host event, not an agent tool. It removes
  all old facts permanently from the active wire, preserves their original check
  provenance in bounded retirement history, prevents ID reuse and never refunds
  cumulative budgets. Returning from scope A to B to A cannot resurrect facts.
- The evaluator independently replays the ledger and derives finite evidence
  states without importing broker or policy implementations. It checks the full
  declared schedule, consumed criteria, truth labels, evidence citations and
  before/after revision summaries. It reports false causes, false refutations,
  unjustified findings, abstentions, recall, requests, disclosure and cost.
  `next_check_accuracy` stays `null`: these controls have no independently
  labelled next-action oracle.

The policies run under the same maximum three observations, nine cost units and
256 Rust rule applications. Rust rule use, including hybrid advice, is charged
from measured kernel output. The ready-agent has an episode deadline of 120 s,
at most eight model calls, 512 generated tokens per call, 8,192 context setting,
32,768 observed aggregate tokens, a 30 s HTTP timeout and bounded IPC frames.
Reports contain measured model usage when the provider supplies it; a missing
usage receipt is an unavailable policy outcome. `ledger_and_findings_safe`
records the absence of an unsafe ledger/finding, including an honest unavailable
result. `mechanical_safety_passed` additionally requires completion, so an
unavailable/inconclusive policy cannot pass that gate. These are bounded research
controls, not a hostile-code sandbox or proof of a platform's resource quota.

The model sees only `request_check` plus the framework's structured final-response
schema. It has no shell, arbitrary URL, filesystem, debugger or native-write tool.
The worker receives a small environment whitelist without credentials/tracing/
proxy variables. Its explicit endpoint must be `http://127.0.0.1:PORT`, with no
path, user information, redirects or proxy lookup. The operator is responsible
for selecting and pinning the trusted local model runtime and weights. Model
name alone does not attest weight identity. Neither a model package nor an
executable selected by the operator is treated as untrusted executable code.

## Corpus and licenses

`diagnostic_pilot/cases/manifest.json` binds file size and SHA256. The 14 public
cases are **owned synthetic development controls** under the repository MIT
license. `generate_development.py` is their authoring script, not a holdout
generator. It covers an export before/after pair, call context, typed receiver
shape, present-with-Undefined semantics, unavailable observations, two-step
conflict repair, source/runtime correlation, foreign revision, consent,
unsupported scope and coexisting findings. All provenance is explicitly
`heldout: false`, `native_verified: false`. No ITS, customer configuration,
private traceback or externally licensed source material is included.

A real comparison still needs separately authored cases, leakage controls,
independently labelled useful checks, licensed source/before-after material and
native runtime receipts for the intended 1C versions/contexts. This loader
intentionally refuses a caller merely relabelling these public cases as heldout
or native evidence. Add a separately reviewed ingestion contract before adding
such data. A passing enum/control suite cannot close that acceptance gap.

Code and case data inherit the root MIT license. Optional LangChain/LangGraph
packages have their own MIT licenses. An Ollama runtime and model weights are
separate operator-provided artifacts with their own licenses; they are not
downloaded or bundled by this tool. Preserve those licenses and exact digests in
any actual experiment receipt.

## Run without a model

Use Python 3.11 or newer. From this directory:

```sh
python3.11 -m unittest discover -s tests -v
python3.11 -m diagnostic_pilot.run --policies fixed one_pass \
  --output /tmp/pilot-baselines.json
```

The optional framework test is explicitly skipped if its packages are absent.
It uses a controlled local HTTP peer and actual framework classes, not a real
model. Install the optional packages and rerun to exercise that test.

Build the unmodified experimental Rust source from the repository root with its
pinned toolchain, into a separate build directory:

```sh
CARGO_TARGET_DIR=/tmp/diagnostic-pilot-rust \
  cargo +1.92.0 build --locked --release \
  --manifest-path rust/diagnostic-core/Cargo.toml
shasum -a 256 /tmp/diagnostic-pilot-rust/release/rentgen-diagnostic-core
```

Supply the **actual hash printed on your machine**, not a historical Linux or
release hash. The adapter verifies it before and after each invocation. From
this directory:

```sh
python3.11 -m diagnostic_pilot.run --policies fixed one_pass rust \
  --rust-binary /tmp/diagnostic-pilot-rust/release/rentgen-diagnostic-core \
  --rust-sha256 ACTUAL_64_HEX_DIGEST \
  --output /tmp/pilot-rust-baselines.json
```

The known two-step development control exposes an avoidable Rust abstention;
this harness preserves that result. It does not modify the frozen kernel or
hide the case from the schedule.

## Optional real ready-agent

The public APIs are the official
[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents) and
[ChatOllama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama).
Direct versions are pinned in `requirements-ready.txt`; the generated universal
`requirements-ready.lock` includes exact transitive versions and package hashes.
This is an isolated development dependency set, not a Core dependency.

```sh
python3.11 -m venv /tmp/diagnostic-pilot-env
/tmp/diagnostic-pilot-env/bin/python -m pip install --require-hashes \
  -r requirements-ready.lock
/tmp/diagnostic-pilot-env/bin/python -m unittest discover -s tests -v
```

Start a separately installed, explicitly selected Ollama runtime and model on a
loopback endpoint. Record runtime version/hash, actual weight digest, license,
hardware and command separately. This tool never installs a runtime, pulls a
model or changes its serving process. A bounded one-case development smoke is:

```sh
/tmp/diagnostic-pilot-env/bin/python -m diagnostic_pilot.run \
  --policies ready_agent --case-id 1 --model EXPLICIT_LOCAL_MODEL \
  --endpoint http://127.0.0.1:11434 --output /tmp/pilot-ready-smoke.json
```

Omit `--case-id` for the whole public development corpus. `--policies hybrid`
also requires `--rust-binary` and `--rust-sha256`; all legal checks still come
from the common broker. The model is allowed to fail or abstain; do not retune
controls against one smoke and call them an independent benchmark.

Reports bind corpus manifest, criteria, source-file hashes, interpreter,
observed framework versions, dependency lock, prompt/settings and supplied Rust
hash. A source change during an episode refuses receipt creation. They retain each decision/reveal, cumulative
cost/disclosure, measured model usage and the original declared pair revisions.
Selected subsets have `whole_corpus_schedule_complete: false`. Output files are
created exclusively, so a previous receipt cannot be silently overwritten.
Exit status is `0` for mechanically completed episodes, `1` for an invalid or
unsafe episode and `2` for an inconclusive runtime/policy outcome. Completion
alone makes no competence, native or architecture decision.

The first actual small-model development smoke on 2026-10-15 used Ollama
0.40.4 and `qwen3:0.6b` on macOS arm64. The operator separately verified the
runtime and model artifact digests. Each diagnostic run made one actual model
request (768 input / 404 output tokens), performed no evidence checks, and ended
`inconclusive`: the framework returned a null structured decision. Finite
diagnostics identified the missing decision without storing model text. The
prompt, model settings and corpus were not adjusted to turn that result into a
pass. This is negative evidence for that bounded candidate exercise, not an
environment-missing result, a competence acceptance or an architecture ranking.
Historical receipts preserve their executed source version; an earlier summary
used a safety flag to mean only no unsafe finding, before the completed-gate
distinction above was added. Do not reinterpret that flag as a passed model run.

## Verification boundaries

Standalone tests cover hash tampering, strict JSON admission, hidden-outcome
separation, consent/repeat/cumulative budgets, partial bundles, incompatible
shape, fact limits, timeout accounting, A→B→A retirement, evidence citations,
forged ledgers/receipts, incomplete schedules and changed criteria. The actual
framework tool-loop test checks the closed tool inventory and measured calls.

The current subprocess cleanup is exercised on macOS/POSIX; Windows process-tree
cleanup, actual native 1C checks, licensed independent holdout, full-model
competence, host memory quotas and production integration remain unqualified.
No GitHub CI, release or production readiness is asserted by a local test run.
