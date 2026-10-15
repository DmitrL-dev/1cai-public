# Internal Linux capture backend

`LinuxCaptureBackend` is a frozen, explicitly selected Linux/amd64 backend. It
does not accept a path-based `GraphBuilder`, execute shell commands, or fall back
to Windows capture. Public dispatch, read capability admission and installed
qualification are separate integration responsibilities.

The backend binds an absolute scanner executable and its exact lowercase SHA-256.
The executable must satisfy the owned scanner's static CGO-disabled ELF,
descriptor transport, sealed-image and process sandbox contract. A backend with
both scanner fields absent can replay an already committed receipt; it cannot
start a new capture.

`capture(ctx, expected_head=..., operation_id=..., authorize_capture=...,
cancelled=...)` first validates the trusted context, canonical operation UUID and
expected project head, then performs the existing authorized receipt lookup.
An exact replay requires current `project:read` and `analysis:run`, and the exact
original expected head. It does not require the current head/configuration to
remain old, a live source root, an installed scanner, or resuming the original
authorization/cancellation callback. State database access is still required.

For a new operation the route is:

1. Authenticate and retain the current entire source configuration and expected
   head, with an absolute operation deadline started at backend entry.
2. Run actual F2 capture; admit the copied owner only after successful F2 exit.
3. Open a fresh exclusive complete-generation owner and give its borrowed private
   `sources` directory capability to the owned Linux scanner.
4. Obtain terminal scanner output and successfully close its process owner before
   building a bounded in-memory SQLite graph bundle from copied source bytes.
5. Seal the generation, including final manifest last, full file inventory/hash
   and real SQLite validation. Successfully exit the generation and copied owner.
6. Verify any existing same-content catalog locator outside a write transaction,
   then perform one short catalog/head/receipt compare-and-swap.

Neither scanner processing nor graph/file validation occurs under the write
transaction. Source and generation attempts remain as unpublished orphans on
failure. This module does not reuse an attempt UUID, overwrite/delete/rename a
tree, repair permissions, or implement garbage collection.

All stages share current analysis authorization, head/configuration checks,
PID/thread ownership, cancellation and an overall deadline of at most 120 seconds.
Each component retains its own shorter phase limit. Parent memory accounting
includes copied source/manifest images, scanner chunks and joined outputs, the
32 MiB bounded sealed executable image and two bounded transient chunks, graph images/cache,
derived outputs and assembly verification copies. The retained tree descriptor
limit reserves the executable ancestor chain plus a conservative fixed transport
allowance before the scanner runs. These are image/retained-descriptor accounting
bounds, not a hard process RSS limit. Go's memory target is independently soft.
Source count, total bytes, file size, paths, inventory, graph VM work and output
sizes have independent bounds; their maxima are not a throughput qualification.

The final cancellation callback runs immediately before entering the bounded
write transaction. Inside it, only a pure owner/deadline check runs in addition
to current SQL authorization and exact state comparisons. No arbitrary caller
callback or filesystem operation executes while that write lock is held.

The transaction rechecks current `analysis:run`, exact expected head, the entire
captured `SourceConfiguration` (including root paths), the exact existing
operation binding, and the same complete catalog row whose actual locator was
verified. The verifier's opened catalog must also equal that selected row.
`commit_publication` retains its existing `_insert_catalog` content/layer mismatch
guard and atomically writes catalog/layers, head, receipt, event and outbox.

After a possible commit acknowledgement failure, all owners and the write
connection are already closed. Existing `_reconcile` reads the durable receipt
and requires the exact operation inputs and snapshot. It does not demand the old
head, configuration or unexpired work deadline: a later valid publication cannot
invalidate the earlier operation's receipt. An unreadable receipt reports
`PUBLICATION_OUTCOME_UNKNOWN` and does not invent success.

The complete-generation proposal is a trusted in-process result of successful
owner cleanup, not a revocable file lease or a security boundary against code
running as the same OS user. Private POSIX paths and repeated mutation checks do
not prove a filesystem-wide atomic snapshot or exclude post-verification
same-user mutation. No stronger files-plus-SQL atomicity claim is made.

`test_linux_capture.py` distinguishes actual Linux/amd64 full-process capture
from native POSIX storage/CAS controls using real F2, generation and SQLite with
constructed scanner bytes. The native fixture uses
`RENTGEN_TEST_LINUX_SCANNER` and optional matching
`RENTGEN_TEST_LINUX_SCANNER_SHA256`, or builds the real scanner with
`CGO_ENABLED=0` using the available pinned Go toolchain. Missing Go on actual
Linux is a failed qualification prerequisite, not a successful skip. macOS tests
do not pretend to be Linux; full capture is refused before source/executable IO.
Local controls do not establish GitHub CI, installed-product, native 1C/EDT or
full-release readiness.
