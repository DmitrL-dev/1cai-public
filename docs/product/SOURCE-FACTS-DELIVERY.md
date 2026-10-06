# Installed-wheel source-fact smoke

`scripts/verification/verify_source_fact_delivery.py` checks one exact wheel in
a new Linux virtual environment against three separately reviewed, SHA-256-pinned
images. This is a narrow handwritten-input delivery check. It does not qualify
Designer serialization, compilation, receiver binding, runtime behavior, measured
accuracy, customer projects, Windows/macOS, MCP or Companion delivery.

## Review before execution

Review the verifier source and record its SHA-256 before running it. Build the
wheel separately using the reviewed build environment; record the exact wheel
SHA-256. Keep existing prepared release/development assets immutable. Pass each
expected executable hash from independent build/review evidence. Do not obtain
"expected" hashes by blindly digesting arbitrary supplied executables.

Run from an ordinary Python 3.11+ Linux interpreter, without `-O`. The script
requires Linux procfs matching the interpreter's PID namespace, `waitid`, and
permission to establish its own child subreaper. It refuses preexisting children.
This is standalone qualification code, not an importable process framework.

Example (replace only the exact reviewed wheel and new output paths/hash):

```sh
python -I -B scripts/verification/verify_source_fact_delivery.py \
  --wheel /absolute/candidate/rentgen_core-0.1.0.dev18-py3-none-any.whl \
  --wheel-sha256 REVIEWED_WHEEL_SHA256 \
  --expected-version 0.1.0.dev18 \
  --input-core /absolute/reviewed/rentgen-input-core \
  --input-core-sha256 8a374c45b52ae9f66e73d64fa1aedd4e30acac15ca2709a00927b6b297581a04 \
  --source-scanner /absolute/reviewed/bsl-source-facts \
  --source-scanner-sha256 70b7ea071e193384ff1d89c9554fa0bb253d6c9c0d9f513eedb089b2cc7d8b7a \
  --source-kernel /absolute/reviewed/rentgen-source-facts \
  --source-kernel-sha256 cf4c06981106d1546023d3cb8b6f4d3e588c8c8e6eaf1b67e3171072cf213d05 \
  --output /absolute/new/source-fact-delivery
```

No download is performed. All input pins are checked before output creation or
process launch; verified bytes are copied into the new private output directory.
Pip installs the copied exact wheel with `--no-index --no-deps --no-cache-dir`.
Every Python command uses isolated mode and runs outside the source checkout.
The installed package's version, module location under the new venv, and isolated
flag are checked. The process environment has a fresh HOME and TMPDIR, and no
inherited customer credentials/profile configuration.

## Checks and artifacts

1. Create a private identity, registry, project/source sentinel and empty head.
2. Create a byte-deterministic owned ZIP with handwritten caller/candidate BSL,
   restricted CommonModule XML, and unrelated canaries. It is never extracted.
3. Invoke installed `python -I -B -m rentgen_core source-facts` with all three
   pinned images. Check the exact selector, Export=true, Server=false, accepted
   entry hashes/sizes, unverified membership/completeness, and both relations
   remaining `unknown`. Source text and absolute output paths must not escape.
4. Repeat the command and require equality of the complete `result`. Outer
   invocation request IDs are intentionally excluded from deterministic equality.
   Every command JSON rejects duplicate object keys (including escaped aliases)
   and nonstandard numeric constants. Both complete success/error streams and
   decoded content are checked for source canaries and the private output path.
5. Supply a wrong archive hash. Require exit 2, empty stderr, exactly the closed
   `SOURCE_FACTS_INPUT_REJECTED` error with fixed text, UUID and empty details.
6. Compare the whole owned workspace fingerprint after each command, including
   source, state, registry, private identity, input, new sidecars and root residue;
   verify the project head is still unchanged and empty.

`commands/<step>/stdout.bin` and `stderr.bin` preserve exact bytes, including
empty streams. Each `command.json` records argv, deadline, exit, stream hashes
and cleanup status. `receipt.json` records the result and exact artifact pins;
`before.json` and `after.json` record post-run residue/source preservation, not
a syscall audit. Identity/registry artifacts belong only to this synthetic run.
The output directory is private (0700); do not publish it wholesale.

Each subprocess has an explicit deadline. On error the verifier kills/reaps its
retained Popen child and verifies/reaps adopted direct children using kernel
ownership checks. Any adopted-child safety cleanup fails the smoke; it cannot
be reported as proof of product cleanup. Cleanup uncertainty is a hard failure.
The verifier does not signal by process name or an unverified PID. Its timeout
cleanup is an outer safety measure, not a replacement for the separate lifecycle
fault-injection qualification. The first SIGINT aborts the run; repeated SIGINT
is ignored while that interruption unwinds through cleanup.

Pure verifier regression checks are in
`tests/unit/test_source_fact_delivery_smoke.py`; they do not launch Core or the
native helpers. Run them after source review, then run the installed smoke and
inspect the persisted streams/receipt. A script in the tree, a unit-test pass or
a built wheel is not evidence that the installed smoke ran successfully.

Frozen contract: [SOURCE-FACTS-PROTOCOL.md](SOURCE-FACTS-PROTOCOL.md).

## Separate CI gates

The candidate remains Core `0.1.0.dev18` / Companion `0.1.19`. Accepted dev17 /
Companion `0.1.18` artifacts remain immutable. Adding this workflow is source-only
preparation; it is not evidence of an executed or successful GitHub-hosted run.
Review and authorization to publish/execute the candidate must precede that run.

`.github/workflows/source-facts-ci.yml` adds the separate required check
**Linux source facts (176 + installed wheel)** on `ubuntu-24.04`. Existing Product
checks, Windows native jobs, portable Linux checks and their job names remain.
All of them remain prerequisites to product acceptance; this source-fact check
cannot substitute for Windows parity or the Linux baseline comparison. Repository
required-check settings are separate administration, not changed by this file.
Do not publish an accepted candidate while this check is absent, pending or failed.

The new job uses the existing commit-pinned checkout/setup/upload actions, Python
3.11.9, Go 1.25.5 (`GOTOOLCHAIN=local`) and Rust 1.92.0. Both Rust images use
`--locked --release`; Go uses `-mod=readonly -trimpath`. The C compiler identity
is recorded. Ubuntu's [strace 6.8-0ubuntu2](https://packages.ubuntu.com/noble/strace)
package is explicitly selected, and its executable SHA-256 is pinned for that
run. Linux Go contracts, including Linux-only ownership tests, run with
`go test -count=1 -p 1 -timeout 120s -json ./...` and retain their real exit status
and JSON event stream. Installation does not change ptrace/security settings. A denied or unavailable
trace gate fails qualification; there is no permission workaround or fallback.

The action checkout is only the transfer source. The exact CI commit is cloned
into a new `$RUNNER_TEMP` checkout, with native targets, Go caches, Python tools,
build outputs and evidence in sibling directories. No test cache or bytecode may
appear in the reviewed checkout: the supervisor rejects ignored files too.
The fixed same-job builds produce exactly three product images and one C fault
probe. The pins record their exact hashes, build commands and compiler identities,
the five fixed harness source hashes, probe source hash, frozen protocol hash,
source commit, strace hash and required denominator 176. `source-sha256.json`
records the complete tracked file inventory at that same commit.

These CI pins attest bytes built by the reviewed fixed workflow from its exact
source commit. They are not arbitrary caller-supplied executables, historical
local image hashes, a signed supply-chain attestation, or a cross-machine
reproducible-native-build claim. The job checks the preserved dependency/license
inventories and uses the existing hash-locked Python build-tool requirements;
test tools keep the existing `requirements-test.txt` pins. It builds a wheel
directly and again through the sdist and requires byte equality. The sdist's
explicit allowlist continues to include both `PLATFORM-SUPPORT.md` and
`PORTABLE-CORE.md`, the source-fact documentation and verifier, Go sources, both
Rust crates and lockfiles, dependency provenance and complete Rust license
bundles. The Go standard-library BSD license, PATENTS and selected original
source notices have their own [inventory](../../go/THIRD_PARTY_NOTICES.md); CI
checks those bytes against its exact Go 1.25.5 installation before qualification.
It does not bundle third-party dependency source caches.

The default supervisor must pass **176/176**, with zero failed, skipped or unrun
variants, confirmed cleanup and no remaining owned descendants. CI never passes
`--polling-correction-only`, weakens the denominator, filters an individual case,
uses `continue-on-error`, or converts missing prerequisites to skips. Only then
does the installed-wheel smoke run with the exact same three image pins and the
new wheel hash. Its 11 recorded commands must pass too. Downloaded artifacts alone
are not acceptance: inspect the job conclusion, full176 summary/JUnit and the
installed receipt for the same source commit.

The historical first local full run was **168 passed / 8 failed**: four polling
failures, two pre-hello ptrace gate timeouts and two strace EPERM failures. The
polling correction and its separate four-case scope do not replace a full run.
Local tracing remains blocked and unaccepted; the GitHub-hosted job is a separate
platform qualification proposal, not a retry to defeat local restrictions or a
claim that the prior local run passed. No local ptrace retry/security change is
authorized by these instructions.

### Ordinary tests and the mandatory supervised lane

Only these three new Linux-only modules are excluded from the existing ordinary
Windows and full-Linux pytest invocations. Pure host and verifier tests remain in
ordinary collection, and no global pytest skip/ignore policy was added:

```sh
python -m pytest -q --tb=short \
  --ignore=tests/unit/test_source_fact_runtime_boundaries.py \
  --ignore=tests/unit/test_source_fact_lifecycle_completion.py \
  --ignore=tests/unit/test_source_fact_wire_receipt_gaps.py
```

The existing Windows CI command additionally retains `-n 3 --dist=loadfile
--max-worker-restart=0` and its JUnit report. The Linux diagnostic command retains
its real exit code and baseline comparison, rather than claiming the complete
product suite is green:

```sh
mkdir -p output
set +e
python -m pytest -q --tb=short \
  --ignore=tests/unit/test_source_fact_runtime_boundaries.py \
  --ignore=tests/unit/test_source_fact_lifecycle_completion.py \
  --ignore=tests/unit/test_source_fact_wire_receipt_gaps.py \
  --junitxml=output/linux-diagnostic.xml > output/linux-diagnostic.log 2>&1
status=$?
set -e
python scripts/verification/check_linux_baseline.py \
  --junit output/linux-diagnostic.xml \
  --baseline docs/product/evidence/linux-baseline-classification-20261005.json \
  --pytest-exit "$status" --output output/linux-baseline-comparison.json
```

The existing baseline's 90 failures / 2 errors are unchanged. The commands above
are ordinary-suite checks only. Bare all-pytest still honestly requires the
supervised modules' prerequisites and does not qualify them by omission.

After independent source/build/pins review and authorization on a permitted
Linux host, the separate full qualification command is:

```sh
/absolute/tools/bin/python -I -B \
  /absolute/clean-checkout/tests/fixtures/source_facts/boundary_supervisor.py \
  --root /absolute/clean-checkout \
  --pins /absolute/reviewed/pins.json --pins-sha256 REVIEWED_PINS_SHA256 \
  --output /absolute/new-evidence/full176
```

Keep all outputs outside that clean checkout. Follow it with the installed-wheel
command in the earlier section, using those same image hashes. The workflow
contains the exact fixed build and pin-generation commands for its hosted lane.
It does not invoke the separate legacy-byte replay, consume private journals,
read withheld source-cohort inputs, or claim source-fact accuracy, binding,
Designer/runtime or whole-product Linux acceptance.

### Retained artifacts

Upload is scoped and runs on failure as well, with 14-day retention: tool
identities, exact source/image/probe pins, distribution hashes, Linux Go JSON
events, pure-test JUnit,
full176 summary/JUnit/streams, named lifecycle measurement files and synthetic
trace streams, and the installed smoke's receipt, command records/streams and
before/after fingerprints. Failed runs retain their failure evidence; absent
later stages remain unrun. Candidate wheel/sdist are development artifacts.
Only after both required gates succeed are the three native images staged with
the root MIT license, the Go 1.25.5 notice/provenance inventory and both complete
Rust notice/provenance/lock bundles.
The native bundle is retained as `experimental-source-facts-linux-amd64.tar.gz`
with its own SHA-256, preserving executable modes through artifact download.
Extract it with `tar -xzf` into a new directory before use. The C fault probe,
virtual environments, caches, source/state registries and
identity-profile trees are not distributed. Never upload the entire private
qualification or installed-smoke directory.
