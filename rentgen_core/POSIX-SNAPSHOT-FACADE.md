# POSIX retained read facade

`PosixSnapshotSources` and `PosixSnapshotGraph` are request-owned readers of one
catalogued generation. Every resolve/list/read/graph call opens a fresh actual
`open_posix_snapshot_session`, verifies copied retained bytes and a real owned
SQLite image, and discloses its result only after successful session exit and
reauthorization. No live-source or pathname graph fallback exists. Sessions are
closed before return; facade use across fork/thread or reentrant callbacks is
denied. A new facade may reopen the same catalogued snapshot in a fresh process.

The existing source cursor/filter/version and graph envelope/capability DTOs are
shared. Graph results remain bounded static calls, with quality unavailable,
source-path identity and temporal atomicity not proven. The extracted source
pagination function is pure; Windows/default delegation retains its behavior.

Actual Linux `ContextResolver` uses the POSIX eager verifier and facade. Its two
optional overrides require `PosixSnapshotLimits` and `VerifiedGraphLimits`.
Defaults explicitly bound copied images to 2560 MiB, resident image accounting
to 4 GiB, graph images to 2 GiB, 20,000 source entries and 1024 retained FDs.
These are accounting ceilings, not allocations, hard process RSS, performance
qualification or a 100,000-file claim. All bounds are checked per operation;
there is no automatic budget widening or fallback after refusal.

No Windows session/path adapter, capture/publication admission, command group,
CLI/MCP tool, snapshot-diff or metadata admission is changed. The facade has no
`_path`. Its `read_session` method is a zero-IO `CAPABILITY_UNAVAILABLE` refusal
for legacy Windows retained-session consumers, never a session compatibility
adapter. Metadata, drafts, diff and native materialization remain unadmitted.
macOS filesystem and real
SQLite tests use constructed scanner records; they do not qualify actual Linux
resolver dispatch, scanner process isolation, capture or native 1C behavior.
