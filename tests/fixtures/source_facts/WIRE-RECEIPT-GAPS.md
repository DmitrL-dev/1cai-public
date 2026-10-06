# Finite public W/R completion adapters

Source-only changes based on the independent 2026-10-05 acceptance gap audit.
No tests, collection, candidate invocation, or build is claimed by this patch.
The protocol remains frozen at SHA-256
`ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.
No production source or independent source-cohort data is changed or consulted.
Independent source review and explicit parent release must precede execution.

## Denominators and controls

`tests/unit/test_source_fact_wire_receipt_gaps.py` adds exactly **42 pytest cases**:

- 14 host scanner-receipt mutations, including five existing weak-code variants
  replayed with exact closed errors and nine missing role/dependency/span cases.
- 11 host kernel-output mutations: scope, all three observations and receipt IDs,
  the two unknown relations, assurance, and an extra field.
- 11 actual Go framed variants: 1.0, 1e0, depth 13, exact 1,500,000-byte request,
  entry ID 4095, start 524288, start/end 524289, escaped admitted keys/enums,
  and ordinary/escaped duplicate keys.
- 5 actual Rust framed variants: exact 65,536-byte request, depth 13, ordinary
  duplicate key, and XML/caller or XML/candidate collisions with coherent receipts.
- 1 actual Rust replay showing that a shape-valid assertion remains unauthenticated
  and cannot rescue forged Go evidence at the host receipt boundary.

Each parametrized mutation runs its exact admitted control first. Host-only
controls test the host validators, not actual scanner provenance. The UTF-8
negative preserves exact selection/receipt equality while splitting a verified
Cyrillic scalar. The same-file control uses one admitted routine and coherent
entry/hash/size records; its negative changes only one role's admission record.
Host failures must raise the one expected fixed CoreError with empty details,
return no result, and emit no stdout/stderr. No stronger binding is inferred.

Framed tests launch the pinned, sealed current Go/Rust image, consume the exact
hello before sending bytes, pump all pipes with a bounded deadline, close stdin,
require exact response extent/EOF/exit, and confirm direct-child reap. They use
the existing qualification supervisor for external ownership protection. Negative
outputs are the complete closed error bytes, not prefixes or exception categories.
Interior JSON whitespace supplies the reachable request-cap controls. The
root-depth-13 payload includes an otherwise forbidden nested field: its measured
claim is a full-envelope closed rejection, not isolation of a depth-only cause.

`go/internal/sourcefacts/wire_test.go` retains every existing mutation. It adds
three strict-request variants and five inclusive/framed bound subcases, along
with admitted family controls. All 13 existing buffer-validation/precedence rows
now compare the complete returned error envelope instead of discarding bytes.
All Go error-byte comparisons use a test-owned literal map, independent of the
production `ErrorResponse` helper used by `Evaluate`, so production serialization
changes cannot self-confirm the oracle. The historical 0.0/0e0 variants remain alongside the exact 1.0/1e0 gaps.

`rust/diagnostic-core/tests/source_facts_contract.rs` retains the existing matrix
and its unchanged **896 combinations: 59 accepted, 837 rejected**. Every accepted
row must equal the submitted closed field graph minus the private receipts table,
plus only `source_facts_host_asserted_no_binding_no_runtime`; both relations stay
`unknown`. Every rejected row must be exactly `Error::InvalidEnvelope` with no
successful partial result. The existing incoherent XML collision rows remain;
two coherent collision rows and one ordinary duplicate row are additional controls.

These denominators describe different layers. Do not add matrix rows, unit-test
PASS events, host cases, or historical replay origins into an acceptance score.

## Covered audit IDs

The Go changes address `W.go.request.literal_1_0`, `literal_1e0`,
`depth_13_closed_error`; all five `W.go.bound.*` entries; and all ten named
`W.go.buffer.closed_error.*` entries in `next-tests.json`.
The Rust changes address `W-R-duplicate-ordinary`, `W.rust.audit_gap.0` through
`.4`, and `W-R-every-success-assurance`.
The host module addresses all nine `W.host.scan.*` role/dependency/span gaps,
all five `W.host.scan.closed_code.*` gaps, all eleven `W.host.kernel.*` gaps,
and `W.host.valid_rust_cannot_authenticate_go`.

The actual legacy CLI adapter documented separately in `README.md` addresses
`R.synthetic.complete_exact_output` and `W.rust.audit_gap.5`: **156 current
unique executions**, mapping **249 preserved historical occurrences**, with
raw stdout/stderr digest and status oracles. It does not synthesize serialization
expectations or make a historical executable-identity claim.
Optional per-slot unavailable-receipt and extra-diagnosis expansions, and a new
full input-core Rust unit run, are deliberately not new mandatory thresholds.

## Passive input-core regression capture

`input_io_capture.py` and the opt-in autouse fixture in
`tests/unit/test_rust_input_workflow.py` support `R.input.exact_retained_io`.
The existing module has a source-enumerated **47 pytest cases**. Its assertions
are unchanged. After review, set `RENTGEN_INPUT_CORE_CAPTURE_DIR` to an existing,
empty, authorized evidence directory outside the checkout during that exact suite.
Unset leaves historical test behavior unchanged. This is a recording mode, not
an assertion that a new run passed.

Per-case directories use a hash of the exact pytest node ID and retain:

- Exact fixture-produced ZIP bytes; exact member data supplied to `writestr`;
  exact buffers passed to `.zip`/`.new` writes, including truncated/replacement
  archives. No source path is reopened by the recorder.
- Actual successfully transferred input-core stdin/stdout/stderr bytes and pipe
  EOF/transfer events, observed only through a module-local `os` proxy.
- Session image hash, PID and terminal status already known to the existing
  owner; fixed exception code/type; pinned test, production module and recorder
  source hashes; hashes and sizes of every retained byte file.

The recorder neither launches nor kills/reaps children, changes authorization,
reads arbitrary archive paths, follows symlinks/FIFOs, nor intercepts global OS
I/O. Existing process ownership remains responsible for cleanup. It observes
fixture writes without substituting their content. The per-case recording cap is
256 MiB. Every append or transfer-recording failure latches an independent
recorder failure. Fixture teardown fails on that latch even if production mapped
an earlier I/O exception to an `INPUT_CORE_*` error accepted by a negative test.
A manifest retained after such an error is labelled `capture_status: failed`; it
cannot count as a successful byte capture.

**Explicit limits:** direct ZipFile containers retain exact member inputs plus
the pinned generator, not reconstructed raw container bytes. Concurrently
mutated archives retain the generated starting/written buffers and exact wire
request/hash, without claiming a stable accepted-file snapshot. Parent-death
probe child-process internals are not intercepted by the in-process recorder;
their existing pinned driver/report remains separate evidence. Successful
`export-analyze` subprocess CLI calls also execute their input-core sessions
outside this recorder. Each observed CLI helper return is listed in the case
manifest with command, exit status, and `input_core_wire: unobserved_out_of_process`.
The status is not a raw-byte capture. An empty `sessions` list establishes only
that no in-process session was observed; it must never be interpreted as proof
of prelaunch rejection or absence of successful child execution. Prelaunch
denial remains an assertion of its specific test. Host CLI presentation is not a
raw input-core wire, and is not relabelled as one. A reviewer must carry these limits
into `R.input.exact_retained_io` rather than imply complete captures where none
were observed.

## Qualification scope

A passing replay establishes only these finite public mechanics at pinned bytes.
The source core remains a prototype: receiver binding and runtime relation are
unknown, native/Designer qualification is absent, and the separate failing full
Linux baseline is unchanged. P lifecycle/disclosure/syscall work and any new
independent source qualification have their own evidence and stopping conditions.
