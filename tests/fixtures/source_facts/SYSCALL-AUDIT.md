# Syscall observation adapter: narrow corrections and remaining blockers

This is an interpretation contract for the owned synthetic Linux source-facts
audit. It does not change native binaries, dumpability hardening, tracing
permissions, the 176 variants, the 600-second harness budget or product deadlines.
Pure parser tests and reinterpretation of retained traces are not fresh native
qualification or an installed-wheel pass.

## Absent loader metadata

The adapter permits exactly the decoded call
`access("/etc/ld.so.preload", R_OK) = -1 ENOENT (No such file or directory)`.
It is an observed failed metadata lookup, not a file-content read. The raw path,
mode and complete result must match, including after pairing split trace lines.
The allowance is recorded under `absent_loader_probes`, separately from runtime
reads. `/etc/ld.so.preload` is not added to the trusted-file list. Successful
checks, other errors or modes, normalized path aliases, opens (even failed ones),
other metadata operations and other missing files receive no new authority.

## Missing observations stay incomplete

The retained push run at public source commit
`215d1c99e2fd6107225aed40d2320712ae8a3d5e` and the PR run at merge commit
`7254136169e1bd13d892a1df0df4bbf8659c595d` for that head each finished
**174 passed / 2 failed**. Their reviewed lifecycle-adapter bytes match.
All four syscall-audit traces contain the absent loader lookup. Beyond it:

- Rust helpers successfully disable dumpability. Subsequent successful writes
  lack decoded descriptor targets; successful `open`/`openat` calls expose only
  pointer addresses instead of pathnames. `statx` arguments are also opaque.
  An expected input path, prior pipe setup or a successful product result cannot
  replace the missing observation. Product hardening must not be disabled to
  make the audit pass.
- The Go helper reads `/proc/self/mountinfo`, `/proc/self/cgroup` and the hosted
  runner's cgroup `cpu.max`. These are outside the current explicit runtime-file
  contract. No general `/proc`, `/sys` or cgroup-file allowance is introduced.
- One push trace has `???( <unfinished ...>` and `<... ??? resumed>) = ?` in a
  Go sibling thread after another thread begins `exit_group(0)`. strace 6.8's
  [syscall decoder](https://github.com/strace/strace/blob/v6.8/src/syscall.c)
  uses `???` when it cannot decode the syscall registers.
  [Exit-event reporting](https://github.com/strace/strace/blob/v6.8/src/strace.c)
  can supply the terminal `= ?` formatting. This explains a possible failure
  mechanism; it does not recover the syscall identity or arguments. The adapter
  explicitly rejects this incomplete observation.
- Independent synthetic review also identified an inherited completion-order
  defect: a syscall entering before the end marker but completing after it could
  be excluded from the active audit. The boundary correction below rejects this
  ambiguity; it does not resolve the independent missing-observation blockers.

The absent-loader correction alone therefore cannot qualify any of these four
traces. A different observation design would need separate review and clearly
stated coverage. The original runs did not authorize privilege changes or local
tracing retries. The separately approved, single-use Actions exception below
does not change that historical result or grant ongoing tracing privileges.

## Split-call boundary correction

Every parsed call retains its `start_line` and completion `line`. Pairing must
match the PID and syscall name; a second entry or completed same-PID call cannot
leapfrog a pending call. Missing completion remains incomplete even if an exit
banner follows. Calls stay in observed completion order, without sorting or
dropping events.

Before interpreting the operation, the adapter rejects any call whose observed
entry/completion interval overlaps the start or end marker interval. It also
rejects `open`, `openat` and `openat2` overlapping any locator-admission marker
(`L:*` or `A`), regardless of the target path. This conservative check also
covers runtime/directory opens and opaque path arguments without guessing their
authority. It includes a completed call inside a split marker write: the
boundary itself is not assumed instantaneous. These cases cannot safely be
assigned to either side of an authority change. A known pipe read may span an
internal admission marker; that marker changes locator-open authority only.
Disjoint calls wholly before start or after end remain outside this audit's
declared operation scope.

Synthetic regressions retain the original unauthorized-open and socket examples
that previously escaped by completing after the end marker. Rejection of those
examples is an adapter correction, not evidence that the native pipeline meets
the remaining audit contract.

## Evidence retention and pure tests

Within the synthetic full-run fixture tree, CI retains only
`**/syscall-evidence/config.json`, `trace-capabilities.json` and
`python-capabilities.json`, alongside the existing raw trace/controller outputs. The config
contains synthetic project paths/ID, state/archive/image paths and hashes, case
selection and runtime roots. It contains no profile bytes or credentials. This
is not a recursive upload of project configurations or user profiles.

The older artifacts did not retain that file. A complete JSON buffer in a trace's
`read(config_fd, ...)` can support a separately labelled reconstructed diagnostic
input. It must not be represented as the retained original file, and raw traces
must remain unchanged.

`test_source_fact_syscall_audit_contract.py` runs in the ordinary pure test lane
and the source-facts CI pure step. It exercises the exact allowance, split-call
pairing, rejected alternatives, unknown/opaque observations and scoped evidence
retention without executing native helpers, ptrace or strace.

## One-shot complete-memory observation diagnostic

The next guarded push from `8cd77af` may use the separately pinned, test-only
`owned_trace_launcher.c` on a disposable Actions runner. It is never installed,
has no setuid bit or file capabilities, and changes no host sysctl or sudoers
file. The short sudo setup reduces to the invoking non-root UID/GID with empty
groups and bounding set, then retains exactly CAP_SYS_PTRACE in the tracer's
permitted/effective/inheritable/ambient sets. A fixed child clears all capability
sets before Python and verifies the actual tracer's post-exec state. Both use
fixed clean environments. No repository token or customer input is passed.

Capability and Python post-exec receipts are retained. The complete raw trace
still rejects opaque pathnames/descriptors and unidentified calls. Namespace
creation is rejected; Rust non-dumpability is checked rather than disabled. The
original 176 cases, time limits, S/E authority assertions and historical failed
results remain. This diagnostic is not a standing grant to future CI jobs.

The existing authority interpreter covers the source operation between S/E,
including native loader/runtime startup. Python bootstrap before S and cleanup
after E are recorded in the raw trace but are not yet fully authority-validated.
Complete bootstrap authority validation, reviewed exact Go runtime-file policy
and genuine timeout/cancellation cleanup through the sudo monitor remain required
before claiming whole-process qualification. Complete decoding is a prerequisite,
not acceptance of those remaining scopes.

## Ordinary CI versus full qualification

The automatic PR/push workflow now runs the fixed 174 non-syscall variants
with the same supervision, failure and cleanup checks. Its receipt explicitly
leaves the two syscall variants unrun and never sets `full176_qualified`.
The strict default remains all 176; `source-facts-qualification.yml` exposes it
as a separate manual workflow, followed by the installed-wheel gate. The old
single-push tracing exception is not part of either workflow. No privilege
expansion, dumpability change or opaque-descriptor allowance is introduced.
A manual run in an ordinary environment can still fail for incomplete observation;
it must not be reported as full acceptance or replaced by the ordinary result.

## Explicit phase/process coverage receipt

`coverage-audit.json` is retained at the exact synthetic `syscall-evidence`
location in both workflow scopes. A denial receipt is initialized immediately
after creating that directory, before config writes, controller launch or trace
assertions. Its initial receipt says phase accounting is unavailable and qualification is false; malformed/undecodable input cannot leave
a success receipt. After parsing and boundary checks, it records syscall counts
and observed PIDs separately for bootstrap, operation, cleanup and marker writes.
Counts partition all parsed calls, including non-overlapping calls outside S/E.
This is syscall accounting, not a complete process-lifetime inventory: signal and
exit banners are not counted as calls, missing trace records cannot be recovered,
and no decoded-path claim is inferred from successful parsing.

Successful process/thread creation results are reported separately from observed
PIDs, including observed PIDs without a recorded creation (apart from the marker
writer) and creation results without observed calls. A matching PID inventory
does not authenticate process identity, establish ancestry or prove every thread
was traced to exit. These remain explicit coverage gaps.

Only the returned `authority-audit.json` marks the operation phase's existing
authority checks as validated. A coverage receipt alone leaves every phase's
authority flag false, even when parsing succeeds. Bootstrap and cleanup always
remain unvalidated, including if the trace contains no calls in those phases.
Synthetic negatives cover forbidden network/path operations and opaque arguments
in both excluded phases: they are counted but never promoted to acceptance.
Unknown syscall identities still fail parsing in every phase.

Marker-shaped writes now require a fully decoded pipe descriptor, exact known
payload with a terminal newline, matching byte count and successful complete
write. All six markers must use the same PID, descriptor and pipe identity;
child-forged or redirected individual markers fail closed. This consistency
check does not independently authenticate the first marker writer or prevent a
coherent forged sequence. The receipt explicitly leaves marker identity
unauthenticated rather than claiming that text markers are a security boundary.

The supervisor receipt adds `whole_process_qualified: false` with unresolved
bootstrap, cleanup, process-lifetime and tracer-cancellation gaps. Its existing
`full176_qualified` flag continues to refer only to the fixed variant suite;
even a future 176-case pass must not be described as whole-process authority
qualification. This change runs no native qualification and grants no additional
runtime-file, descriptor, tracing or privilege authority.
