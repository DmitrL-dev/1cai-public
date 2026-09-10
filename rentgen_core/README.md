# Local project foundation

The base package uses only the standard library for explicit project state, captured source bytes,
and source-bound graph publication on local Windows. The installed `rentgen`
CLI uses a Windows process SID and explicit project/snapshot selectors. The
concrete adapter is the `rentgen_graph` package. Legacy `tools/rentgen` modules
are compatibility aliases during the separate all-consumer cutover.

The root `pyproject.toml` uses an explicit Hatchling backend. Build/install
instructions are in `docs/product/CORE-INSTALLATION.md` in the full checkout;
the source distribution includes `packaging/core/README.md` and the Go scanner
sources. The legacy root `setup.py` is not packaging metadata and must not run.
The optional `mcp` extra pins the official SDK 1.30.0 and enables the local
`rentgen-mcp` stdio entry point (`python -m rentgen_core.stdio_mcp`). Use the
existing audited Windows runtime lock for its dependency versions. Base wheel
installation does not install the SDK. The sdist includes CORE-INSTALLATION,
CORE-MCP, STATE-MIGRATION, PROJECT-ACCESS, SNAPSHOT-METADATA,
SNAPSHOT-READ-SESSIONS, SNAPSHOT-PUBLICATION-ADR and that runtime lock.
The eight stdio tools derive identity from the Windows process SID; source/graph
reads require explicit project and snapshot IDs. Setup and migration remain CLI
operations. Cancellation does not imply rollback; reconcile the original capture
operation receipt. See `docs/product/CORE-MCP.md` for bounds and exact tool schemas.
No HTTP, remote MCP, form/configuration editing, update, observer or full-product
readiness is implied by this local CLI slice. Those acceptance gates remain open.

Version 0.1.0.dev1 creates schema3 projects and provides audited membership
commands and explicit state-upgrade-access (2→3), with verified backup and
operation receipts. Existing schema2 snapshots remain readable. The packaged
metadata API uses bounded retained read sessions and metadata_scan_v2 evidence;
metadata tools are not added to the eight-tool stdio interface. See the delivered
PROJECT-ACCESS, SNAPSHOT-METADATA and SNAPSHOT-READ-SESSIONS runbooks.

The current development checkout additionally creates schema4 projects and
provides durable project drafts through `rentgen_core.drafts` and `draft-*` CLI
commands. Existing schema3 projects require explicit `state-upgrade-workflows`
with verified backup. These additions are not in the previously accepted dev2
wheel. See [draft history](../docs/product/DRAFT-HISTORY.md) for the commands,
receipt recovery, permissions and remaining HTTP/editor delivery work.

## Trusted boundary and use

An authenticated adapter constructs `Principal` from a verified immutable
issuer/subject or local OS binding. Neither a string supplied by the user nor a
frozen dataclass authenticates anyone. The trusted local bootstrap API receives
explicit paths and owner identity. Do not expose `register`, `ProjectState.create`
or arbitrary handle constructors directly to transport payloads.

```python
from pathlib import Path
from uuid import uuid4
from rentgen_core import (
    ContextResolver, Explicit, Principal, ProjectRegistry,
)

owner = Principal("local-os:verified-owner-id", "local_os")
# Parent directories/source already exist; registry file and state directory do not.
registry = ProjectRegistry.create(Path("C:/explicit-local-state/registry.sqlite3"))
project = registry.register(
    owner,
    source_root=Path("C:/explicit-workspace"),
    state_root=Path("C:/explicit-workspace/.rentgen"),
    display_name="Project",
)
ctx = ContextResolver(registry).resolve_context(owner, Explicit(project.project_id))
with ctx.state.transaction(ctx.principal, write=True) as tx:
    tx.require_all({"project:admin", "project:read"})
    tx.set_membership(Principal("verified-issuer:subject-id", "verified_token"),
                      {"project:read", "analysis:run"},
                      operation_id=str(uuid4()),
                      expected_revision=tx.membership_revision())
```

Selection accepts a canonical UUID, never a path, name or alias. Only an absent
adapter selector may become `UseConfiguredDefault()`; the resolver's optional
default must come from trusted adapter configuration. Unknown/blank explicit
values never fall back. Conflicting transport selectors must be rejected by the
future adapter before forming this single selection value.

Registry mappings contain UUID, canonical source/state roots and display label.
Roots cannot overlap a different registered project. Registration performs path
canonicalization; context resolution performs no live-source traversal or reads.
Membership is checked in the selected project state before context is returned.
`source_root` is only a locator and is not a snapshot source capability.

## Authorization and transactions

Memberships are normalized rows keyed by project, principal ID and authority;
permissions are separate foreign-keyed rows. Owner bootstrap grants the explicit
`OWNER_PERMISSIONS` set; there is no wildcard, inferred admin or role-claim import.
Every admitted unit of work requires `project:read`. Membership changes require
`project:admin` in a schema-3 or schema-4 write transaction. `require_all` checks the full set.

The frozen `ProjectState` is a connection factory, not a shared connection. Each
unit of work opens `mode=rw` (never implicitly creating a missing database), checks
project identity and schema, enables foreign keys, and closes on every exit.
Writes use `BEGIN IMMEDIATE`; reads are SQLite query-only transactions. Success
commits, an exception rolls back. Mutable files use WAL. SQLite waits at most five
seconds for ordinary busy locks and returns `STATE_BUSY`; there is no unbounded
retry loop. Do not do parsing, source IO or external effects under a write lock.

A context carries no cached permissions. `require_permission` opens a fresh read
unit of work and sees committed revocation. It is a standalone read check, not
authorization for a later write: mutations must authorize inside their own write
transaction. A read transaction observes the membership snapshot at its start;
revocation affects subsequent units of work, not an already-running read scope.

Only new files/directories are initialized. Registration commits its registry
mapping after state bootstrap. Direct state creation commits schema and owner
bootstrap in one SQLite transaction. On failure it removes only the new database
file reserved by that call and its newly created sidecars; existing database or
sidecar destinations are rejected without overwriting them. Registration exceptions
remove only its exclusively created state directory. A process crash may leave an unregistered directory for explicit
recovery; registry/state/filesystem do not claim a distributed atomic transaction.
There is no automatic migration, attach/move, alias, network-filesystem support,
or protection against direct file mutation by the same OS account. Membership
changes use mandatory caller operation IDs and an administrative revision/CAS.
The same transaction writes permissions and an immutable API audit/receipt row.
Exact repeats reauthorize and return the original receipt without reapplying old
permissions. A competing change fails; callers must retain the original operation
and revision for recovery. Self-lockout and removal of the last existing local
administrator are rejected. The example above creates a new operation; retry it
only with its saved original inputs. See `docs/product/PROJECT-ACCESS.md` for the
actual-SID `membership-list/set/revoke/receipt` CLI and HTTP onboarding workflow.

## Source configuration and publication state

New project databases in this checkout use schema 4; registry databases remain schema 1.
Existing schema-2 projects retain snapshot reads and publication compatibility;
membership changes require an explicit verified `state-upgrade-access` 2→3.
That runner retains a WAL-consistent schema-2 backup and commits schema 3 plus
its exact operation receipt atomically after reauthorization. Pre-v3 executables
reject schema 3, so all processes accessing the project must be upgraded first.
`ProjectState.migrate_v1_to_v2(principal)` is an explicit admin-only transaction;
it rolls back on failure and does not synthesize historical snapshots. The trusted
`state-migrate --backup-directory PATH` runner first creates and verifies a
WAL-consistent SQLite backup, then reauthorizes the existing migration. Its
operation ID identifies backup/recovery, and `migration_attribution=not_proven`
does not claim which concurrent operation changed schema. Existing version 1
membership reads do not silently migrate state. `state-migrate` rejects schema 3
and 4 before backup IO; its original 1→2 attribution remains unchanged.
`state-upgrade-access` still targets exactly 2→3 and rejects schema4. Use the
separate `state-upgrade-workflows` runner for 3→4; it records its own workflow
receipt and preserves existing membership and publication receipts.
See `docs/product/STATE-MIGRATION.md` and `docs/product/PROJECT-ACCESS.md`.

`get_source_configuration`, `configure_source_layers` and `get_project_head`
provide ordered base/extension roots and revision-based compare-and-swap. Layer
roots must be disjoint and stay under the registered source root. Registration
rejects current links/reparse points; it is not a guarantee against later path
replacement. A nested project state directory is excluded by its exact path.

The trusted transaction method `commit_publication` checks current permission,
source revision, full expected head and operation identity, then writes catalog,
head, receipt, event and pending observer outbox atomically. Its return value is
only durable after the enclosing transaction commits. Savepoints also preserve
state when a caller catches a failed multi-step operation inside that transaction.
An exact existing operation receipt returns its historical head after later
publications/configuration changes; conflicting reuse fails. This method does
not verify filesystem bytes itself. The public `capture_and_publish` orchestration
below verifies the complete generation before using this transaction method.

## Retained source capture on Windows

`rentgen_core.capture.capture_sources(ctx, expected_head=..., operation_id=...)`
authorizes `analysis:run` and checks head/configuration before opening source
files. It creates an exclusive staging directory and returns `CapturedSources`
with canonical source metadata and retained raw bytes. It does not publish a
snapshot or advance project head. `read_bytes(entry)` checks exact membership,
confinement, size and hash; `decode_bsl(entry)` separately requires valid UTF-8.
Unsupported text encodings and opaque companion files are retained as raw bytes.

The Windows reader pins ancestor/leaf handles, rejects reparse points and unsafe
paths, compares 128-bit file identities, and streams two content passes with
metadata inventories around them. Actual tests cover NTFS junctions, replacement,
rename/write locks, Unicode collisions and cleanup. ReFS was not exercised and
ordinary file symlink tests require a privilege unavailable on this test host.
Unsupported handle/filesystem APIs fail explicitly; there is no path-based fallback.

Capture limits are 64 MiB per file, 1 GiB total raw bytes per pass and 100,000
inventory objects. Exceeding one returns `SOURCE_CAPTURE_LIMIT_EXCEEDED`.
BOM/newlines are preserved. Only the exact registered nested state subtree is
excluded. Captured hashes prove retained bytes, not that all live files coexisted
at a single instant: `temporal_atomicity=not_proven` remains explicit.

## Snapshots and errors

`SnapshotRef` validates a project UUID and matching lowercase SHA-256 snapshot
ID/manifest hash. It pins a value; it does not prove captured bytes or publication.
A project without a published head returns `snapshot`, `sources`, `graph` all
`None`. `require_snapshot` returns `SNAPSHOT_REQUIRED` for that context. Otherwise
the resolver selects head once, with its catalog entry in the same authorized
read transaction, and verifies manifest, retained sources, graph and derived input
hashes before returning capabilities. Explicit missing IDs return
`SNAPSHOT_NOT_FOUND`; no other project or newer head is searched.

## Captured graph publication and pinned reads

The trusted composition root explicitly injects the concrete scanner and reader;
the stdlib core never imports HTTP, private graph data or a quality model:

```python
from uuid import uuid4
from rentgen_core import capture_and_publish, get_project_head, read_source
from rentgen_graph.snapshot_adapter import (
    RentgenCapturedGoBuilder, RentgenGraphReaderFactory,
)

resolver = ContextResolver(registry, graph_reader_factory=RentgenGraphReaderFactory())
ctx = resolver.resolve_context(owner, Explicit(project.project_id))
result = capture_and_publish(
    ctx, expected_head=get_project_head(ctx), operation_id=str(uuid4()),
    builder=RentgenCapturedGoBuilder(Path("C:/explicit-tools/bsl-scan.exe")),
)
pinned = resolver.resolve_context(owner, Explicit(project.project_id), result.snapshot.snapshot_id)
page = pinned.sources.list_entries(limit=100)
ref = pinned.sources.resolve("base", "CommonModules/Example/Ext/Module.bsl")
raw = read_source(pinned, ref)
module = pinned.graph.resolve_module(ref)
impact = pinned.graph.impact(ref, depth=1)
```

Build the supported scanner from this repository's `go` directory with
`go build -buildvcs=false -o <explicit-output> ./cmd/bsl-scan`. Its version/hash,
normalized NDJSON, coverage, graph hash and raw source bindings are retained.
Empty and zero-routine inputs are valid when strict scanner coverage confirms them.
Quality is explicitly unavailable; identity remains unresolved/source-path-only.

Each attempt exclusively reserves `generations/<random canonical UUID>` and keeps
its Windows no-follow directory/ancestor pins through capture, graph build,
verification and commit. The physical UUID is neither the operation ID nor a
source identity. The snapshot ID remains the canonical manifest SHA-256. There
is **no generation rename**: Windows strong parent pins conflict with that
operation. Complete files, hash/binding checks and flush precede the single
catalog/head/receipt/event/outbox transaction. This protocol change is recorded
in [the publication ADR](../docs/product/SNAPSHOT-PUBLICATION-ADR.md).

An interrupted or losing attempt remains an unregistered orphan. Directory
existence never grants read access; there is no automatic garbage collection or
orphan promotion. Retrying a precommit operation explicitly starts a new physical
attempt. Repeating a committed operation returns its exact historical receipt,
even after later head/configuration changes. Conflicting operation bindings fail;
CAS never retries against an implicitly refreshed head. New operations with
identical content reuse the existing verified catalog locator and still record
their own head revision/receipt/event. If an acknowledgment is lost and the exact
receipt cannot be read, the result is `PUBLICATION_OUTCOME_UNKNOWN` with operation ID.

Source and graph capabilities retain the same `SnapshotRef` and reauthorize each
public call. Source refs require exact snapshot/layer/path/hash equality. Source
pages are bounded to 1..200 entries, with cursors tied to project, snapshot, page
size and the last layer ordinal/path. Impact depth is 1..5. Graph queries retain
no-follow file and ancestor handles across the entire explicitly immutable,
read-only SQLite query; corrupt bytes or journal sidecars fail. Later live source
edits or head changes cannot change pinned results.

Publication and retained readers currently require the supported Windows handle
adapter. The capture qualifier remains `working_tree_verified_passes_v1` with
`temporal_atomicity=not_proven`: this is not structural apply/release acceptance.
File flush plus SQLite commit does not promise power-loss durability on every
storage stack; missing/corrupt committed files fail honestly after recovery.
Legacy HTTP/CLI/MCP/UI and source enrichment services still require the E1–E4
cutover. Their existing live-root/global-graph paths are not made safe by this API.

Domain/SQLite failures use `CoreError.code` and `to_dict(request_id)` with
`error: {code, message, request_id, details}`. Trusted bootstrap filesystem errors
(e.g. an existing destination file) remain ordinary Python filesystem exceptions;
an eventual transport bootstrap adapter must map them explicitly. No HTTP status
mapping, authentication transport or API fallback is implemented here.

## Verification

Run the dedicated `tests/unit/test_project_core_*.py` files with
`python -m pytest -o addopts=''` and Ruff on `rentgen_core` plus those test files.
Tests create only their own temporary files and include A/B simultaneous context
resolution, concurrent writers, revocation, require-all, FK constraints, rollback,
bootstrap failure, unknown/default/blank selection and source-IO refusal.
