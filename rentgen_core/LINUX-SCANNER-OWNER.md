# Internal fixed Linux scanner owner

`_linux_scanner.open_linux_scanner()` owns one exact verified Go scanner image on
Linux/amd64. This is an internal prerequisite for a future graph adapter. It does
not enable capture, publication, public capabilities, native tools or a general
process runner. Existing Windows scanner adapter and strict command stay intact.

## Trusted API and exact data

The trusted caller supplies an absolute scanner locator and its expected SHA256,
an active private retained `Directory` containing a newly materialized captured
source tree, mandatory `LinuxScannerLimits`, authorization and cancellation callbacks.
The directory remains caller-owned and must stay active and unchanged through
owner exit. Input materialization, source/manifest binding and complete artifact
assembly are the caller's separate responsibility. This API accepts no shell,
arbitrary arguments, output pathname or model-selected executable.

Entry uses the existing Rust input executable copier: no-follow ancestor/leaf
opens, regular single-link bounded image, trusted UID/mode, pre/post stamp/hash,
then a sealed Linux memfd. The child executes that image through its inherited
FD. A bounded header check requires static ELF64 little-endian amd64 `ET_EXEC`,
without interpreter/dynamic program headers: the accepted build uses
`CGO_ENABLED=0`, not PIE or external shared-code dependencies. Changing the original
locator cannot change the executed bytes. This reuses
the copier only, not Rust session ownership or Rust protocol. Input root is passed
through descriptor-relative `openat(".")`, with the same held identity and an
independent enumeration cursor. No original input pathname is reopened. Passed
descriptors must be distinct and above stdio.
The environment contains only fixed locale values; no inherited loader/Go knobs.

The explicit non-generator owner permits only its entry PID/thread. Foreign,
forked and reentrant calls/exits refuse before teardown. `__enter__` returns after
the fixed HELLO; the child has not read source content yet. One `scan()` sends GO,
then returns frozen `LinuxScannerOutput(ndjson, coverage, executable_sha256,
protocol="rentgen-owned-scanner-linux-v1")`. Output is disclosed only after all
stdout/stderr/coverage EOFs, status zero, confirmed reaping and current permission.
Coverage travels through an owned pipe, never a file read back by pathname. Raw
stderr is bounded and discarded. A graph adapter must still validate exact raw
coverage, source hashes, records and physical spans before using these bytes.

## Native ownership and limits

The Linux/amd64 entry locks its Go OS thread, sets parent-death SIGKILL and checks
the expected parent PID, establishes no-new-privileges and non-dumpable policy,
arms a kernel monotonic SIGKILL timer, and installs a process-wide seccomp TSYNC
filter before HELLO. Only zero TSYNC return is accepted. The filter checks amd64
architecture and refuses x32, fork/vfork, process clone, exec and namespace changes.
Go thread clone remains available; clone3 returns ENOSYS for safe clone fallback.
The independent-process prohibition applies to every existing/future runtime
thread. There is no descendant process to detach or retain inherited pipes.

PDEATHSIG observes the creating parent **thread**, which must remain alive until
owner close. It is not a Windows Job, cgroup or general sandbox. The filter is a
narrow fixed-scanner policy, not a security boundary for arbitrary executable
hashes or a future syscall ABI. Source audit finds only standard-library/internal
Go packages and lexer/regex extraction; no subprocess/network/plugin/native BSL
execution path. Changing that implementation requires requalification.

The timer includes waiting for GO and blocked pipe reads/writes; setup failures
refuse without a degraded fallback. Python independently pumps all pipes through
a selector and checks the absolute deadline, current authorization, cancellation
and held input namespace before/after work. Cleanup kills an unfinished child,
waits at most two seconds and closes all acquired pipes/selector. Unconfirmed
cleanup fails success; an existing denial/cancellation/body error remains primary.
Native startup and kernel termination are not a real-time scheduling guarantee.

The descriptor scanner inventories bounded entry names, limits depth/path length,
rejects links, special files, cross-device children, hardlinks,
nonprivate UID/mode and access/default ACLs. It reads each held regular descriptor
into at most its prechecked size plus one, then compares stamps and namespace.
All regular leaves, including XML/binary assets, count toward file/source limits
and undergo private ownership/ACL and namespace checks. Only BSL suffixes have
their content read/extracted and appear in coverage. Non-BSL content hashes are
not established by this scanner: complete generation verification remains the
caller's responsibility. There is no live-source pathname fallback. These are observed mutation checks,
not leases or protection against hostile same-UID/root/mount activity.

Typed limits cover source/file bytes, file/entry/depth counts, stdout, coverage,
stderr, transport read count and deadline. Descriptor traversal holds at most
depth plus two input descriptors, separate from pipes and Go runtime descriptors.
The source maxima remain 1 GiB total and 64 MiB per file;
these are rejection ceilings, not accepted workload/performance claims. The
mandatory parent resident budget covers immutable pipe chunks plus their joined
outputs (two byte images), one read chunk, bounded HELLO and a conservative 256
bytes per configured nonempty transport read for chunk/list and join-view metadata. The read
count is separately capped before retaining another chunk, preventing fragmented
output from creating unbounded metadata. This uses no growing bytearray capacity.
The existing sealed executable adds up to 32 MiB kernel image
storage and copier chunks. Caller's input tree/retained images, metadata, Python
overhead, native process and graph/scanner consumer allocations are separate.
Go's explicit memory target is a **soft GC target**, not a hard RSS limit: lexer,
function/token/query objects and JSON construction have additional allocation.
No 1 GiB throughput, hard RSS cap or concurrent-session aggregate is promised.

## Qualification boundary

Linux tests execute the actual built scanner, sealed image, pipes, private files,
parent SIGKILL, native timer and syscall refusal from a real post-filter process.
Fault seams only force denials. Non-Linux runs do not pretend to be Linux. Native
Mac Go tests and Linux cross-compilation establish their stated source/build
scope only. Actual Linux/amd64 and installed CLI integration were separately
qualified at [PR #102, HEAD `366db69`](../docs/product/evidence/development-ci-366db69-20261016.json).
That scoped receipt does not qualify the future offline installed SDK, larger
workloads or subsequent bytes. No public capability is admitted by this module.

Kernel interfaces: [PDEATHSIG](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html),
[seccomp TSYNC/ABI](https://man7.org/linux/man-pages/man2/seccomp.2.html),
[kernel timer](https://man7.org/linux/man-pages/man2/timer_create.2.html).
