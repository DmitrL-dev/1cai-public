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
stated coverage; privilege changes and local tracing retries are not authorized.

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

CI retains only `**/syscall-evidence/config.json` within the synthetic full-run
fixture tree, alongside the existing raw trace/controller outputs. The config
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
