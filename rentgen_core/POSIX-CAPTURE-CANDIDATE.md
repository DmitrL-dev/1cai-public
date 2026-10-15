# Internal POSIX source candidate boundary

`_posix_capture_candidate.open_posix_capture_candidate()` constructs one private,
unpublished source candidate from the actual `PosixLiveTree`. It is an explicit
internal context, not public capture, a scanner/process owner, graph build,
publication, resolver, identity or OS capability admission. Existing Windows code,
capture dispatch, state schema and retained readers are unchanged.

Inputs are trusted `ProjectState`, authenticated `Principal`, registered source
root, exact `ProjectHead`, typed candidate/live limits, and a trusted request
authorization callback. Current `analysis:run`, head and configuration are checked
in short state transactions before/after native IO and builder disclosure. No
SQLite transaction is held across source copy or fsync. The configuration used by
the actual live reader is the current state configuration bound to that head.

## Owned source-only layout

The state root must already satisfy the private POSIX directory policy. A private
`staging` directory is created or validated through the held state-root descriptor.
Each attempt exclusively creates `staging/<fresh canonical UUID>` with descriptor
relative `mkdir`; EEXIST never grants ownership or resumes a previous attempt.
The first observed child identity is checked again after fsync/open. All source
subdirectories are exclusively created through held private parents, without
pathname mkdir/open or chmod/ACL repair. Source leaves are exclusively created
0600, fsynced, then verified once through a held private read descriptor against
the same inode and immutable live bytes. No generic primitive was changed.

The candidate contains `sources/<layer>/<relative path>` and the canonical
**source-only** `source-manifest.json`. Empty declared layer roots are present;
empty live directories participate in inventory comparisons but are not source
manifest entries. There is no graph, derived scanner output, final `manifest.json`,
published generation or catalog record. A future orchestration owner must consume
and remove this auxiliary source manifest before assembling a final generation;
it cannot advertise this layout as a complete snapshot.

The first live inventory pins the real source descriptors. Pass one copies each
bounded immutable image, hashes/decodes it, writes it through owned descriptors and
verifies the private copy. A second inventory and actual second held-FD content
pass must match. A third inventory and successful live-reader exit precede builder
access. Source links, special/multiple-link files, collisions, device changes and
observed namespace/stamp changes are refused by the real live reader.

The candidate retains the exact first-pass immutable source bytes. Its
`project_id`, `source_digest`, `entries` and `read_bytes(CapturedInput)` satisfy the
narrow captured-tree input contract. `source_document` and `source_revision` are
also available within the context. Builder reads return those verified images
with current authorization and held private-leaf stamp/name checks. They do not
reopen live or candidate content paths. Replacing/deleting the original live tree
after entry cannot change the copied inputs. Builder output paths and scanner
lifecycle are deliberately not supplied by this layer.

## Durability, failures and orphans

All written leaves and their containing directories are fsynced by the existing
owned writer. The complete source candidate is then inventoried exactly and its
directories fsynced bottom-up, followed by staging/state directories. Success exit
repeats inventory, durability and authorization checks before issuing a compact
`source_verified_candidate`, `published=False` receipt. The receipt is diagnostic
source evidence, not catalog authority, a reusable capability or a commit result.

**Every created attempt remains on disk on every outcome.** A partial write,
entry failure, cancellation, unknown fsync outcome, failed builder or successful
source-only exit leaves an unpublished staging candidate/orphan. Resource cleanup
closes every acquired live/private context and clears buffers; it never recursively
deletes, unlinks, renames or promotes by pathname. Replacement of the attempt or a
child therefore cannot cause cleanup to delete foreign contents. A retry uses a
new UUID; automatic reuse, orphan promotion and garbage collection are absent.
Any future cleanup/promotion policy requires a separate owned namespace contract.

## Explicit limits and lifetime

`resident_byte_budget` is mandatory. After bounded metadata inventory and before
content copying, the plan reserves all source images plus the greater of a
transient file/decoder allocation and canonical manifest construction/readback.
The file term includes the grow-detection byte, a decoder input slice and a
conservative four-byte Unicode character image. The manifest term reserves nine
times its preflight UTF-8 upper bound: two four-byte Unicode images for serializer
chunks and their joined output, plus UTF-8 bytes. This also covers two immutable
manifest images during private readback. Preflight
counts canonical JSON lengths without first allocating a complete JSON image;
the final document is still produced and validated by the canonical manifest
helper. Unknown schema growth fails rather than silently exceeding the bound.

These are conservative large-image accounting terms, **not a hard process RSS
cap**. Live inventory/configuration, canonical validation and normalized path
containers, Python/allocator overhead, buffered stream state, state SQLite and
caller-retained images/results are additional allocations. Builder/scanner/output
memory and concurrent candidates require separate caller budgets. The maxima
remain 64 MiB per live file, 1 GiB source bytes, 100,000 source entries and 64 MiB
source manifest. Those maxima do not qualify 1 GiB throughput or RSS behavior.

The candidate reserves the complete configured live-reader FD cap plus its own
actual ancestor/child/leaf descriptors and a transient enumeration slot before
opening another retained object. Mutable state SQLite descriptors are separate,
owned by their existing transaction contract. Candidate depth, builder-returned
byte totals and deadlines are independently bounded. Builder-returned bytes are
charged even when a caller retains several references to the same image.

The explicit non-generator context permits only its entry PID/thread and rejects
reentrant/foreign/forked operations or exits before teardown. Ordinary owner
failure closes the entire capability; cleanup receives the original exception
triple and preserves its denial/cause. Locals holding undisclosed byte images are
cleared on failure as well as owner buffers. There is no TTL reaper; explicit
context exit, including cancellation, is required. The at-most-30-second deadline
starts before entry and covers both passes, validation, fsync, builder reads and
exit. Native C calls and blocking callbacks are checked cooperatively, not killed
mid-call. POSIX descriptors are not leases; whole-tree temporal atomicity remains
`not_proven`, and hostile same-UID/root/mount changes remain outside the boundary.

## Evidence boundary

Tests use real POSIX live files, private candidates, state authorization, actual
mutations and fsync/descriptor IO under pytest's default temporary directory.
Fault seams only force negative paths; no fake OS or Windows handles qualify
success. This is not scanner ownership, live publication or installed capture
acceptance. Linux filesystem/ACL/runtime CI on the integrated source and final
Windows regression CI remain necessary.
