# Internal POSIX copied generation session

`_posix_snapshot_session.open_posix_snapshot_session()` is an explicit internal
opt-in, not a resolver, publication, capture, identity or public capability route.
It requires trusted `ProjectState`, authenticated `Principal`, exact `SnapshotRef`,
a verified-byte graph factory, `PosixSnapshotLimits`, `VerifiedGraphLimits`, and a
trusted authorization callback. The retained root is derived from `state.path`;
there is no second independent generation locator or current-head fallback.

The existing Windows `SnapshotSources`/`SnapshotReadSession`, path/handle leases,
public capability table, resolver and transports are unchanged. This module does
not make Linux/macOS snapshot operations available to callers of those APIs.

## What is owned and verified

Entry checks current `project:read` and the selected catalog record. The private
state root, `generations` and exact catalog child (hash or UUID) are opened through
the existing no-follow POSIX directory primitives. Every retained descendant is
also opened as private: current effective UID, directory mode 0700, file mode
0600, no extended ACL, admitted local filesystem and unchanged namespace linkage.
No automatic chmod, ACL repair or identity migration is performed.

The session copies the canonical manifest from its descriptor and binds its hash,
project, source digest and graph hash to the catalog. Inventory rejects unknown
files, links, special files, multiple-link leaves and SQLite sidecars before
reading source/derived/graph content. Directories are limited to file parents,
optional empty `sources`, `inputs`, `build-work`, and declared source-layer roots.
Unknown empty directories and contents under unlisted structural paths fail.
Depth, inventory items and `max_retained_descriptors` are bounded before opening
children. Mutable state SQLite connections are owned separately by their existing
transaction contract; they are not included in the retained-descriptor count.

All sources and both derived inputs are read through held directory descriptors
with exact size/hash checks and pre/post file stamps. Source bytes remain private
immutable Python `bytes`; derived inputs are verified then discarded. SQLite gets
the exact copied graph and canonical manifest through the verified-byte reader.
It independently checks SQLite integrity, schema, keys, counts, provenance and
source bindings. There is no original-path SQLite open or path-only fallback.

Entry/post-copy/exit inventories compare known file and directory stamps and
namespace links. These observations do not detect every temporary mutation
between observations. POSIX descriptors do not exclude writers or renames, and
copies are neither Windows leases nor an atomic filesystem snapshot. Same-UID
hostile code and arbitrary trusted Python adapters are outside this boundary.

## Explicit resource contract

Both session budgets are mandatory; neither is a process RSS cap:

- `copied_byte_budget` bounds cumulative manifest + sources + derived + graph
  bytes, up to the existing 2.5 GiB session maximum. File size and the remaining
  budget are checked before `stream.read(size + 1)` allocates an immutable copy.
- `resident_byte_budget` accounts for retained manifest/source byte images plus
  the larger of a transient derived image and two graph images during one native
  SQLite deserialize. The extra grow-detection byte is counted. This plan is
  checked before source/derived/graph copying. Caller-selected graph image limits are
  also checked before graph copying; the graph maximum remains 1 GiB. No helper
  `MAX_BYTES` was increased and no 1 GiB workload acceptance is claimed.
- This is per-session accounting. There is no shared reservation across sessions;
  snapshot diff must not use it until its caller supplies an aggregate budget.
  Callers must account separately for retained results, concurrent sessions and
  references they keep after close.
- Manifest parsing, Python containers/allocator overhead, buffered-stream state,
  SQLite cache/temporary structures and SQL results are additional allocations.
  Graph row/value/result/VM/cursor limits remain independently required; see
  `VERIFIED-GRAPH.md`. No hard native malloc/RSS bound is implied by these values.

One bounded `read(size + 1)` produces the immutable image; this code does not
collect chunks and join or make a second full Python graph copy. The graph reader
performs one native deserialize. Sources are copied before graph deserialization;
derived buffers are discarded before the graph is loaded. Large C reads,
deserialization and blocking authorization callbacks are cooperatively checked
before and after, not forcibly interrupted mid-call.

## Lifetime and disclosure

The returned context is an explicit non-generator owner. Only its entry PID/thread
may use it. Public calls and exit reject foreign/forked/reentrant access before
advancing private generator contexts or invoking SQLite. The real owner can still
use and finally close a context after a refused foreign exit. Reentry is invalid.

`entries()`, `manifest_bytes()`, `read_source(SourceRef)`, `resolve_module(SourceRef)`
and `module_impact(SourceRef, max_depth=..., max_edges=...)` authorize before and
after preparation, including graph serialization. Source references must match
the exact selected snapshot, spelling and hash. Current catalog equality and
`project:read` are checked on every authorization checkpoint; the trusted hook may
add request authority but cannot replace that state check.

The deadline starts before catalog/descriptor IO and covers entry, reads, graph SQL,
and successful exit. It is at most 30 monotonic seconds. There is no TTL reaper;
the owner must exit, including cancellation. Ordinary owner-operation failure
closes resources and clears owned byte/callback references. Source bytes already
returned, parser structures retained by caller exceptions, and copied results
remain the caller's responsibility.

Success exit verifies inventory/namespace and authorization, closes the graph reader
and all directory contexts, and only then makes `validation_summary` available to
the owner. Cleanup gets the original exception triple; cleanup errors do not mask
an existing denial/body exception. A success cleanup failure cannot report a
successful validation summary. No background cleanup, original-path reopen or
automatic generation promotion is attempted.

## Qualification scope

Tests build real SQLite graphs from explicitly synthetic scanner records, create
private owned retained trees and commit fixture catalogs through the state-only
publication seam. They exercise real POSIX descriptor IO, SQLite and current
membership/catalog checks. They do not stand in for live capture, scanner process
ownership, native 1C, installed delivery, or an end-to-end published generation.
Actual Linux/runtime and Windows regression were separately qualified in the
bounded [PR #102 integration](../docs/product/evidence/development-ci-366db69-20261016.json),
including installed CLI. Local macOS evidence retains its own scope; future
offline installed SDK and subsequent source/bytes require separate acceptance.
