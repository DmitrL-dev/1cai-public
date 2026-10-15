# Internal copied-byte graph assembly

`posix_snapshot_adapter.build_posix_graph_bundle(captured, scanner_output,
limits=PosixGraphLimits(...), authorize=...)` is a synchronous internal graph
prerequisite. It launches no scanner, opens no input/output pathname, writes no
generation, changes no catalog/head/receipt, and enables no public OS capability.
The existing Windows/path adapter remains separate.

The trusted captured owner supplies an exact `tuple[CapturedInput, ...]`, its
`source_digest`, and `read_bytes(entry)` returning immutable verified images.
The caller may retain these images after a successful source-candidate exit;
constructing this object does not independently prove capture. The scanner input
must be the exact `rentgen_core._linux_scanner.LinuxScannerOutput` type and owned
Linux protocol, containing immutable terminal NDJSON/coverage images and the
trusted executable SHA-256. Constructed Python scanner buffers used by unit tests
are not evidence of real Linux scanner execution.

The adapter rechecks every BSL image hash/size/encoding, rejects path collisions,
and uses the unchanged strict scanner validator for exact raw coverage,
declaration counts, physical source spans and call sites. Source inputs and
scanner outputs have explicit byte/entry/record bounds before SQLite starts.
Binary non-BSL entries remain part of capture identity but are not graph inputs.

The only shared builder extension is the private `_populate_store(...,
_records=...)` snapshot-only iterator input. It refuses legacy mode and any
simultaneous path inputs. The legacy/path branch still reads and compacts its
files as before. The copied-byte branch builds an actual `:memory:` SQLite
database with memory temporary storage, a fixed page cap, bounded SQL values,
bounded VM work and current authorization/deadline callbacks. Fresh memory
databases use full auto-vacuum and secure deletion; this branch omits the
path-store `VACUUM`, which requires an internal attached database.
The native progress handler counts each opcode, including repeated short SQL
statements; current authorization/deadline callbacks are batched at most every
1,000 opcodes, with additional explicit source/record/output boundaries.

Before `serialize()`, actual page count times page size must fit the graph cap.
The result must be a self-contained rollback-mode SQLite image. The build
connection then closes, and a separate owned in-memory connection deserializes
the exact returned image. Read-only integrity, foreign-key, schema, counts,
source-module and provenance/hash checks must all pass. Its authorizer uses the
reviewed verified-graph allowlist. Both connections close before the final
authorization check and disclosure. Initial denial precedes source reads and
connection creation. Progress-handler denials preserve their original exception;
cleanup errors cannot replace an active failure. Foreign, forked or reentrant
calls cannot advance or close the operation owner.

Private raw-source, decoded-text, normalized-output and graph locals are cleared
in `finally` scopes, including the public wrapper's input references. Record
generators close deterministically. Failed completed private validator/builder
frames release their input locals without replacing the original authorization
exception or cause. These are reference-lifetime guarantees for this adapter,
not memory erasure: caller-owned input images and diagnostic exceptions from
malformed input can retain their own data outside this adapter's frames.

The frozen `PosixGraphBundle` contains `receipt`, `graph_bytes`, canonical
`ndjson`, canonical `coverage`, `sqlite_version`, and
`resident_image_accounting`. The graph receipt preserves schema 2,
`source-path-v1`, the distinct `rentgen-captured-owned-go-v1` adapter identity,
exact source/input binding, owned Linux protocol/executable hash,
and the existing static semantic scope. Quality remains `unavailable`.

`image_buffer_budget` is mandatory. The conservative large-image preflight
charges caller source images, decoded BSL/line images, scanner canonicalization
images, path/binding images, two graph images and configured connection caches.
The recorded formula is `S + 9*BSL + 16*scanner + 24*path + 3072*entries +
2*max_graph_bytes + 2*cache_bytes`. This is **not a hard RSS cap**: Python
containers/allocator overhead, SQLite sort/staging overhead and native execution
memory are additional. Database pages, VM work, input/output and record counts
are independently bounded. The deadline is cooperative; native calls and strict
JSON validation are checked before/after, rather than forcibly interrupted in
the middle. Scanner-process and concurrent-operation budgets remain separate.

The future publication owner must still verify the complete owned generation,
write the final manifest last, close all source/generation owners successfully,
then perform a short authorized head/configuration CAS and operation-receipt
transaction. This bundle is neither a committed receipt nor proof of real Linux
capture, publication, restart reads, installed packaging, or full product support.
