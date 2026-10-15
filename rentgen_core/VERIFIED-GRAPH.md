# Internal verified-byte graph reader

`rentgen_core.graph.open_verified_graph()` and
`RentgenGraphReaderFactory.open_verified()` provide an opt-in internal seam for
an immutable SQLite graph image plus canonical manifest bytes and an exact
`SnapshotRef`. This is not connected to snapshot resolution, capture, CLI/MCP or
OS capability admission. The existing `open(graph_path=...)` route and its Windows
file/ancestor lease requirements are unchanged.

The new seam takes no filesystem locator. It verifies the manifest hash/project,
graph hash, rollback-mode SQLite header, integrity, foreign keys, schema, keys,
counts, provenance and source-path bindings, then queries exactly one deserialized
in-memory SQLite connection. Replacing or deleting the original file cannot affect
that connection. A path-only factory or missing `Connection.deserialize` is an
error; there is no path fallback. Caller-provided graph and manifest inputs must
be exact immutable `bytes`.

This validates the graph/manifest pair only. It does not verify source/derived
artifacts, directory inventory, ACLs, sidecars or file ownership and cannot mint a
published generation. A future retained-session owner must copy bytes through its
verified descriptor namespace, refuse sidecars/WAL and unsafe private objects,
bind the catalog and verify all other artifacts. A manifest hash alone is not an
authorization credential or an admission of its source claims.

## Memory and work contract

Every call requires `VerifiedGraphLimits(image_buffer_budget=...)`; there is no
implicit memory opt-in. The maximum graph image remains **1 GiB**, independently
of the POSIX leaf helper's current 256 MiB bound. Before opening SQLite, the seam
requires `2 * len(graph_bytes) <= image_buffer_budget <= 2 GiB`. This accounts for
the caller's immutable image and SQLite's one native deserialization copy. The
owner does not deserialize a second image. It releases its input references after
loading; callers are responsible for references they retain.

**This image-buffer budget is not a hard process RSS cap.** In addition:

- Canonical manifest input is at most 64 MiB; parsing creates Python structures.
- Default SQLite cache target is 8 MiB (configurable up to 64 MiB). This is a
  SQLite cache setting, not a native allocator ceiling. SQL temporary structures
  use memory, never an unvalidated temporary directory. Integrity checks, grouping,
  sorting and SQLite bookkeeping can allocate outside the image/cache target.
- SQLite's value/encoded-row length limit defaults to 1 MiB (maximum opt-in 16 MiB),
  SQL text is at most 64 KiB, columns at most 128, attached databases zero and
  worker threads zero. Oversized values fail; they are not silently truncated.
- A private cursor view iterates and charges rows before `fetchall()` accumulates
  them. Default cumulative row-accounting budget is 64 MiB per query (maximum
  1 GiB). Accounting includes a conservative text/row/object charge, not a malloc
  measurement. This also bounds the legacy graph SQL's seed-ID fetch before
  `seed_ids.extend()`. It is separate from the graph image maximum.
- At most 16 live statements by default (configurable up to 64). EOF, one-row
  fetch, error and owner exit explicitly close statements. Only live statements
  are tracked. Retaining a Python exception/cursor wrapper does not leave its
  native statement open.
- Default VM work budget is 10 million progress steps per validation/query
  (maximum 100 million), with quantum `min(1000, max_vm_steps)`. Refusal is
  cooperative at that quantum, with less than one quantum of observation margin;
  this is not an exact native instruction count. A budget below 1000 does not
  receive a hidden 1000-step minimum. Exceeding the budget fails the read.
- Serialized result size is at most 16 MiB by default (maximum 64 MiB), checked
  incrementally before return. This disclosure limit is not the row/peak-memory
  limit. Callers must budget results they retain and concurrent owners separately.

The configured maxima do not establish throughput, peak RSS or acceptance of
all 1 GiB workloads. On the development Mac, real 1/16/64 MiB SQLite payloads
showed approximately one additional image-sized native RSS increase during
`deserialize`; `tracemalloc` did not count that allocation. These small local
measurements are not Linux qualification. Sealed Linux memfd and a private
verified file/FD are alternative designs requiring actual SQLite/FD/lifetime and
memory measurements; neither is implemented by this seam.

## Lifetime and authority

The factory is a context manager and exposes only `resolve_module(exact_path)`
and `module_impact(exact_path, max_depth=1..5, max_edges=1..600)`. There is no
caller-facing execute/cursor, filesystem path, alias lookup or mutable connection.
Only exact BSL/OS/BSP paths in the selected manifest are accepted.

One owner PID/thread may use the reader synchronously. Before/after query and
JSON serialization, during row iteration and SQLite progress, the supplied trusted
authorization callback is invoked; its original exception is preserved. A
callback must check current authority/catalog binding rather than a cached grant.
SQL progress interruption preserves that exact denial. Reuse, fork inheritance,
foreign-thread access and reentrant operations/exit are rejected before touching
another operation's connection. Both factory entry points return the same explicit
context object; no generator wrapper can be consumed by a refused exit. Foreign
or reentrant public-context exit leaves the real owner's final close available.

The default deadline is 30 monotonic seconds from context entry, configurable
only downward. It covers validation, queries and result preparation; it is not a
hard limit on a single C call or a blocking callback. There is no background TTL
reaper: the owning caller must exit the context, including cancellation. Any
ordinary query failure closes the reader and clears owned buffers/callbacks;
subsequent calls fail. Success exit reauthorizes before close. Every live cursor
and the connection gets one explicit close attempt; cleanup failure cannot turn
a failed operation into success or replace its primary exception.

SQLite `query_only` is backed by a deny-by-default authorizer. Only read/select,
recursive-select, the required read-only schema/integrity PRAGMAs and the small
fixed graph function set are allowed. ATTACH, writes, PRAGMA changes and unknown
functions (including load_extension) are denied; extensions are disabled when the
runtime supplies that switch. These restrictions protect the internal fixed SQL
route; arbitrary Python adapters/private reflection and hostile same-process
code are outside the trusted local adapter boundary.

## Verification scope

`tests/unit/test_verified_graph_reader.py` uses real SQLite files/images and the
real graph builder with explicitly synthetic scanner records. It exercises query
parity with the existing path reader, path replacement, schema/digest damage,
closed SQL policy, authority/progress/serialization denial, PID/thread/reentrancy,
resource budgets and cleanup while retaining exceptions. It does not substitute
POSIX descriptors for Windows handles or exercise a fake capture. Native POSIX
fork coverage is skipped on hosts without `os.fork`.

Actual Linux runtime execution is still required. This layer does not advertise
Linux/macOS snapshot access, capture, scanner process ownership, native execution,
installed delivery, or a complete published generation. Windows file-lease
regression coverage remains required on the final integrated source commit.
