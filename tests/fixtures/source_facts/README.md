# Finite public legacy CLI byte replay

`legacy_byte_replay.py` is a standalone, test-only Linux adapter for the **actual
current `rentgen-diagnostic-core` executable**, with no CLI arguments. It does
not import the candidate library, build software, invoke tests, collect pytest
cases, or read hidden fixtures. This source addition is **unexecuted**. Independent
source review, reviewed pins, and an explicit run release must precede execution.
The replay flag is an accidental-launch guard, not a substitute for that release.

## Frozen public input and primary oracle

The sole input cohort is `rust/diagnostic-core/tests/observed-wire/manifest.json`
and its 17 named shards. The pinned manifest SHA-256 is:

`caa015d7a9b39aeedf3cadb8856b4f3a6529e757fb565e0eb58ac4201855490a`

That manifest pins each shard's original bytes/hash, with **156 unique inputs**
(132 semantic JSON, 24 protocol errors), covering **249 historical requests**
(225 semantic JSON, 24 errors). The 93 duplicate occurrences are historical
mappings, **not 93 additional current executions**. Full completion launches
exactly one legacy CLI process per unique input; there are no warm-ups or retries.

The public vectors already contain `recorded_stdout_sha256`,
`recorded_stderr_sha256`, and the exact `expected.process_exit_code`. These are
the primary regression oracle. The adapter hashes the current process's **raw
stdout and stderr bytes**, including whitespace and final LF, and compares
against those historical hashes. It never serializes the expected JSON to invent
an expected byte stream. Exact-type structural JSON equality is supplementary:
object ordering is irrelevant, array ordering matters, and `true`, `1`, and
`1.0` are different. Protocol errors additionally require the closed structural
object `{"error": expected_code}` and exit code 2.

Before any child launch, every origin is reconciled with the already-authorized
original journal, whose SHA-256 is:

`4ad23df65b996bc181684f377f238b8927595052ff50c518bb635aa24c24fd5a`

Reconciliation includes exact start/finish line numbers, historical sequence,
tag, input byte count/hash, stdout/stderr hashes, exit status, and type-exact
response. All 249 call indexes must occur exactly once. Original origin fields,
including cohort, fixture ID, variant, policy and step where present, are retained.
The word `heldout` in historical public-origin metadata does not make this replay
a new hidden evaluation. No hidden path or additional fixture is consulted.

## Reviewed pins and source provenance

Use a separately reviewed JSON pins file, then independently supply its SHA-256.
The exact top-level keys are:

- `schema`: integer 1
- `source_commit`: full lowercase 40-character commit of the reviewed build
- `source_sha256`: map from every path in the adapter's `REQUIRED_SOURCE` set to
  its exact SHA-256. This pins this adapter, this README, the frozen source-fact
  protocol, all ten Rust production source files, Cargo.toml, Cargo.lock, and the
  legacy diagnostic PROTOCOL.md. Extra or omitted paths are rejected, and the
  actual crate `src` file inventory must match. These are candidate/adapter
  source checks, not a declaration that dependencies or system libraries are sealed.
- `image`: exactly `role`, `path`, `sha256`, `build_source_commit`, `build_command`,
  `compiler_identity`. Role must be `legacy_diagnostic_cli`; path is the absolute
  current executable path; the digest must match the independent CLI argument;
  build source commit must equal `source_commit`. The nonempty command string
  array and compiler identity document the independently reviewed build and are
  **never executed** by this adapter.
- `journal`: exactly `path` (absolute original journal path) and `sha256` (the
  fixed historical journal hash above)
- `public_manifest_sha256`: the fixed public manifest hash above
- `expected_unique_inputs`: integer 156
- `expected_origins`: integer 249

The adapter directly verifies source bytes and sealed executable bytes. The
commit/build metadata are **reviewed declarations**, not a reproducible-build
proof or an independently verified Git HEAD check. The reviewer must verify the
build-to-source linkage before issuing the pins. Historical image hash
`fe72906aac9f0bbf30e2a9e09c44b927c4b7b0e5a5618b1703a107d5c0b77c70`
is retained as historical provenance only. The current image needs its own new
pin; relinking does not imply historical ELF identity.

The frozen source-fact protocol hash remains
`ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.
This adapter neither changes that protocol nor routes legacy inputs through the
new source-fact entry point.

After review and a separate explicit release, the command shape is:

```text
python3 -B tests/fixtures/source_facts/legacy_byte_replay.py \
  --root ABSOLUTE_REVIEWED_CHECKOUT \
  --pins ABSOLUTE_REVIEWED_PINS_JSON --pins-sha256 REVIEWED_PINS_HEX64 \
  --image ABSOLUTE_CURRENT_LEGACY_ELF --image-sha256 CURRENT_IMAGE_HEX64 \
  --output ABSOLUTE_NEW_EVIDENCE_DIRECTORY \
  --run-reviewed-public-replay
```

The output parent must already exist; the output directory must not and must be
outside the reviewed checkout. The adapter
creates it exclusively with mode 0700 and never overwrites an earlier run.
Run with ordinary, unoptimized Python on Linux with memfd seals and pidfd support.
The image must be a regular, single-link, executable file owned by root/current
UID and not group/other writable. Symlinks in its absolute path are rejected.

## Bounded execution and ownership

The adapter copies the image from an opened descriptor to an owned memfd while
hashing it, verifies unchanged file metadata, installs and checks write/grow/
shrink/seal seals, and executes `/proc/self/fd/N`. It never hashes a pathname then
executes mutable bytes at that pathname. This small test-local implementation
mirrors the production `_executable` primitive without importing product code.
The exact same sealed current image is reused for every sequential invocation.
Only stdio and the sealed image descriptor are inherited, with a minimal fixed
environment and no shell.

For each child, its `Popen` is retained before pipe/selector setup. A pidfd is
retained for exact-child signalling. If acquiring that pidfd itself fails, cleanup
uses only the retained, unreaped direct `Popen`; no other thread or handler reaps
children. No process-name search, PID scan, blanket signal, or process-group kill
is used. All catchable paths close the selector, kill when necessary, wait/reap,
and close all three pipes and the pidfd before parsing, writing receipts or
releasing any report. Unconfirmed cleanup is terminal and stops subsequent
launches. SIGINT/SIGTERM set a cancellation flag, so repeated signals do not
interrupt cleanup with another exception.

Stdin writes and stdout/stderr reads are simultaneously nonblocking, and select
waits never exceed 100 ms. Limits are 65,537 stdin bytes, 1 MiB stdout, 64 KiB
stderr, five seconds per child, and 900 seconds from evidence setup through the
sequential run, plus at most a separate two-second cleanup interval for a child
at a failure boundary. Bounds apply to the owned transport and checked loops;
regular local filesystem operations and process creation rely on the trusted OS
and are not claimed to be interruptible in a stuck kernel. Cap failure preserves
at most cap+1 bytes as a witness and explicitly marks the capture incomplete;
it never treats that prefix as complete output. A failed or timed-out child may
leave undrained bytes after termination; EOF and completeness flags expose this.

These are test-driver cleanup mechanics, **not** a general descendant sandbox,
network/filesystem confinement, proof of parent-death behavior, or protection
against killing the driver with SIGKILL or an uninterruptible kernel task. The
reviewed legacy source has no child-launch behavior. No native service is called.

## Retained evidence and finite denominator

For each attempted `wire-NNNN` directory:

- `request.bin`: exact public bytes intended for stdin
- `stdin.bin`: exact prefix successfully written to the pipe; successful cases
  require the full request and explicit stdin close. This measures write delivery,
  not independent proof that the child consumed each byte.
- `stdout.bin` and `stderr.bin`: unmodified captured bytes
- `status.json`: actual process exit code (negative Python signal code when
  applicable), retained child PID, EOF/write/reap/cleanup status, capture sizes/
  hashes, all historical origins, historical hashes/status, and eight individual
  checks. Status is written only after cleanup has been attempted.

`summary.json` retains all 156 planned rows, including unrun cases on interruption,
cleanup failure, or run deadline. It separately counts attempted current processes,
passed/failed/unrun unique inputs, and passed/failed/unrun historical origins with
fixed 156/249 denominators. Every completed status file has its own SHA-256 in the
summary. A receipt-write failure records that case as failed rather than silently
removing the attempted process. If evidence storage itself fails, a complete
summary cannot be promised and the command exits unsuccessfully.

The evidence directory additionally retains the exact reviewed pins, raw original
journal, pinned public manifest/shards, and a 249-row `journal-origin-map.json`.
A full PASS needs every raw stdout digest, raw stderr digest, exact exit code,
structural JSON comparison, complete stdin delivery/close, both output EOFs,
confirmed reap, and successful transport/cleanup. Structural equality cannot
rescue a byte-hash mismatch. A run produces no revised goldens.

A pass only closes the public legacy CLI byte-replay gap at the pinned source and
current image. It does not establish source-fact accuracy, hidden-cohort results,
runtime binding, native Designer qualification, the separate Linux baseline, or
production portability. This source change itself makes **no executed claim**.
