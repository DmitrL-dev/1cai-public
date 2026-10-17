# Immutable snapshot publication without filesystem rename

Date: 2026-09-09. Status: implemented bounded core protocol; transport cutover and
release acceptance remain open.

The original snapshot plan proposed moving completed staging into a hash-named
generation, then committing catalog/head/receipt. Actual Windows tests showed that
the required parent handles denying write/delete sharing block both cross-parent
and sibling rename with sharing violation. READ_ATTRIBUTES-only handles allow
rename but also permit independent parent write handles, weakening the confinement
contract. A preceding lstat/path check would leave a race. That alternative was
rejected after review.

The core now exclusively creates `generations/<random canonical UUID>` before
capture. The UUID identifies a physical attempt, independently of operation ID and
content identity. Candidate and ancestor handles stay pinned with the strong
no-follow sharing rules through capture, real graph build, manifest construction,
flush, complete verification and publication. Live source handles close when raw
capture is sealed. There is no rename, overwrite, replacement of a previous
generation, or copy into an existing generation.

The manifest SHA-256 remains `snapshot_id`. Its source digest binds exact retained
raw bytes and ordered layers; graph provenance and independently hashed NDJSON and
coverage bind the actual scanner inputs. Temporal atomicity remains `not_proven`,
metadata identity unresolved and quality unavailable.

Only the existing SQLite write unit of work publishes the catalog row, head CAS,
operation receipt, event and observer outbox. Authorization and configuration/head
revisions are checked again there. Resolver selects a head and its catalog in one
authorized read transaction and never discovers generations by scanning disk.
Filesystem completeness precedes visibility; atomicity is a catalog guarantee,
not a claim of a filesystem/SQLite distributed transaction.

Unregistered attempts after a process kill, failed build or lost CAS remain
inaccessible orphans. Explicit retry before commit allocates a new physical UUID;
an existing success receipt returns the original result. Identical content from a
new operation reuses the existing verified catalog locator and records a new head
revision/event. After matching receipt replay, the write transaction rechecks exact
head/source revisions and reselects the authoritative catalog locator. Every
legitimate catalog insertion advances head in that same transaction; a concurrent
insertion therefore fails HEAD_CONFLICT before reuse. A changed catalog with an
unchanged head violates the state invariant and fails STATE_CORRUPT. Capture, build,
inventory, hashing and verification all stay outside the write unit; stale
operations never retry against a refreshed head.

Catalog DTOs accept exactly `generations/<canonical UUID>` and the original
`generations/<matching snapshot hash>` form. This keeps existing state fixtures and
explicit old entries compatible without allowing arbitrary relative paths. Normal
new publications always use a fresh random UUID locator. No schema version change
or automatic migration/promotion is needed.

Lost acknowledgment is reconciled by the exact durable operation receipt after the
old state connection closes, including an error releasing candidate pins after
commit. A later head cannot substitute for that receipt. Unreadable receipt state
returns `PUBLICATION_OUTCOME_UNKNOWN`, never guessed success.

Complete-generation validation independently checks required graph tables,
columns, primary/foreign keys, row counts and source-path bindings. An iterative
bounded no-follow directory inventory must contain exactly the manifest-listed
regular files; unlisted status, log and lock files fail publication/resolution.
Source reads pin no-follow ancestors and leaf handles and check exact size/hash.
Graph queries keep those handles through metadata validation and the concrete
read-only SQLite query with `immutable=1`; sidecars are rejected. The core imports
no concrete graph/HTTP adapter. Unsupported platforms fail explicitly.

Tests use public temporary sources and the real Go scanner, actual SQLite files,
Windows junction/sharing checks, injected exceptions, and the separate abrupt
process-death checks below. They cover exact operation replay, same-content
attempts, ABA, source configuration/permission changes, corrupt files and pinned
S1 after S2. An injected exception exercises Python cleanup; it is not evidence
of recovery after forced process termination.

## Abrupt-process publication recovery (development source)

`tests/unit/test_publication_process_kill.py` starts a separate Python publisher,
waits for a marker at a private publication boundary, observes state from the
parent, then force-kills and reaps the publisher. Markers are outside generations.
The harness requires the expected kill exit status, no acknowledgment and no
Python `finally` marker; a premature exit or boundary timeout fails the test.
No production fault-injection flag or cleanup operation is added.

- Windows capture with the real Go scanner is killed before complete verification,
  after complete verification, inside the uncommitted publication transaction,
  and after commit but before acknowledgment.
- Linux/amd64 uses its actual owned-scanner backend and is killed after generation
  completion, inside the uncommitted publication transaction, and after commit.
- Precommit checks observe an unchanged head and no catalog/receipt/event/outbox
  rows both while the publisher is blocked and after its death. Resolver refuses
  the orphan. Explicit retry with the original operation and head allocates a new
  generation; the old attempt remains retained and unreferenced.
- Postcommit checks require the complete catalog/head/receipt/event/outbox unit,
  including same-content catalog reuse. Real retained source and graph reads work
  after the kill. After a later publication and deletion of the live source,
  replay returns the original operation receipt without a builder, another
  generation, another event or another outbox row. The later head is unchanged.
- Two additional portable tests kill a writer around the same SQLite transaction
  using synthetic catalog rows. They prove state recovery only, not scanner,
  retained-file validity, installed-package acceptance or macOS admission.

Boundary markers are atomically renamed outside the generation. The parent waits
for a readable marker while checking that the same publisher is alive and the
harness deadline has not expired. Windows marker open denials are retried within
that deadline; permanent denial, malformed JSON or an exited publisher still
fails. This retries only test-control IO, never capture or publication.

Run the focused suite with `python -m pytest -q
tests/unit/test_publication_process_kill.py`. Native tests require Windows or
Linux/amd64 and the Go toolchain; platform skips are not acceptance evidence.
The full Windows and portable Linux CI suites include these tests.

These are deterministic kills at named boundaries, not interruption inside
SQLite COMMIT, filesystem flush or an OS/power failure. They establish no orphan
removal lease and do not prove that an arbitrary observed attempt is inactive.
Full lifecycle/exclusivity and installed-release qualification remain open.

## Exact generation verification (development source)

`verify_catalog_generation(ctx, generation_relpath, graph_reader_factory=...)`
and the Windows/Linux CLI verify one exact **catalog-referenced** generation:

```sh
rentgen generation-verify --registry /path/registry.sqlite3 \
  --project <project-uuid> --generation-relpath generations/<attempt-uuid>
```

Linux also accepts `--identity-profile /path/identity.json`; its API caller must
supply a verified-byte graph reader adapter. Windows uses the retained SQLite
validator directly. Canonical UUID and matching legacy hash locators work on
schema 2/3/4; schema 1 refuses. Current `project:read` is required before locator
lookup. Unreferenced locators fail with `GENERATION_UNREFERENCED` before retained
IO, even if a complete directory exists. There is no discovery or orphan promotion.

The operation verifies manifest/catalog bindings, every source and derived file,
graph hashes/provenance/schema and the exact file inventory. Windows holds file
handles and checks entry/exit inventories; Linux uses private verified copies
with entry/post-copy/exit checks. Existing session resource bounds apply (30-second
session deadline, at most 20,000 source entries and 2,560 MiB verified/copied bytes;
Linux additionally caps resident image accounting at 4 GiB). Failure, including
missing files or incomplete cleanup, produces no successful verification result.

The initially selected catalog entry must still match when the session begins,
at session authorization checkpoints and after successful session cleanup. A
historical generation remains selectable after a later head; same-content reuse
does not change its physical locator. The live source tree and scanner are not
needed for verification. The CLI rechecks permissions after output serialization,
including error redaction when access was revoked.

Success contains `catalog`, the platform-specific `validation` summary,
`physical_state=verified_at_read` and `removal_permitted=false`. This describes the
completed bounded observation. It is not an atomic filesystem/SQLite snapshot,
ongoing validity guarantee, activity verdict, cleanup lease, power-loss proof or
claim about the current head. Files/catalog may change after observation. No state
mutation, generation removal, release bump or macOS admission is introduced.

`tests/unit/test_generation_verification.py` covers portable refusals and real
POSIX storage fixtures; `tests/unit/test_generation_verification_capture.py`
uses actual Windows/Linux capture, historical/reused and legacy locators, damage,
catalog drift, CLI revocation and a fresh CLI process without live sources.
Native skips on another host are not native or installed-release acceptance.

## Read-only generation attribution (development source)

`get_generation_attribution(ctx, generation_relpath)` and the Windows/Linux CLI
query one exact locator in an authorized SQLite read transaction:

```sh
rentgen generation-attribution --registry /path/registry.sqlite3 \
  --project <project-uuid> --generation-relpath generations/<attempt-uuid>
```

Linux can additionally pass `--identity-profile /path/identity.json`. The locator
must be a canonical UUID or legacy lowercase SHA-256 under `generations/`.
The API requires current `project:read`; the CLI checks it again after output
serialization. Schema 2/3/4 are supported without migration, schema 1 refuses.
No source, graph adapter, directory inventory or generation file is opened.

- `catalog_referenced` returns the exact catalog entry, its latest committed
  publication receipt and `observed_head` from the same read transaction. A later
  head does not hide a historical catalog reference. Same-content publications
  reuse a locator; the latest receipt identifies that catalog publication, **not
  the operation that created the physical directory**.
- `unreferenced_at_read` means this project catalog had no reference to the exact
  locator in that read. An active attempt may commit immediately afterwards;
  it may also be a failed/redundant attempt or a nonexistent directory. The query
  does not infer which. It cannot attribute an unregistered attempt to an operation.
- Both results state `physical_state=not_inspected` and
  `removal_permitted=false`. Catalog presence does not verify retained files.
  Missing or inconsistent receipt bindings for a referenced catalog fail rather
  than returning an unreferenced result.

This is a bounded single-locator diagnostic, not automatic discovery, a cleanup
lease, an orphan promotion or a deletion operation. Tests exercise real SQLite
state, Windows capture failures/retry/reuse/lost acknowledgment, CLI authorization
and a Linux CLI subprocess with absent sources/generations. Source CI does not
qualify a new installed release or expand the macOS platform contract.

No automatic GC or cleanup of potentially committed attempts is introduced.
Future removal still requires exclusive lifecycle ownership, proof that no active
publisher or retained reader can use the attempt, and fresh catalog attribution.
File flushing reduces risk but universal directory/power-loss durability is not
claimed. This ADR does not complete E1–E4 source enrichment/CLI/MCP/HTTP/UI cutover,
canonical metadata identity, structural apply, release readiness or observer
execution. The pending outbox is durable intent, not a completed observer run.
