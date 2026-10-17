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
Windows junction/sharing checks, separate competing publisher processes, and
process kills before/after complete verification and before/after state commit.
They cover exact operation replay, same-content concurrent attempts, ABA, source
configuration/permission changes, corrupt files and pinned S1 after S2.

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
