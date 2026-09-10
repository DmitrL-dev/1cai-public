# Local project MCP over stdio

This is a separate, local-only server for the published snapshot core. It uses
the official Python MCP SDK 1.30.0. It does not mount the legacy MCP application,
HTTP routes, portal handlers or a live 1C proxy.

Run it in the supported Windows Python 3.11 environment with the MCP dependency
installed and a registry created through the local CLI:

```powershell
python -m rentgen_core.stdio_mcp --registry C:\Rentgen\registry.sqlite3 --scanner C:\Rentgen\bsl-scan.exe
```

The console callable is `rentgen_core.stdio_mcp:main`. Packaging/optional-extra
installation is maintained separately by the product packaging profile. This
module never downloads a scanner or discovers an executable through PATH.
`--scanner` can be omitted for reads and replay of a committed operation. A new
capture without a configured scanner returns `GRAPH_ADAPTER_UNAVAILABLE`.

The server authenticates its Windows **process token SID** once at startup.
Registry and scanner paths are trusted process arguments. Tool arguments cannot
set actor, permissions, source root, registry, executable, environment or an
output file. Project memberships are checked again on each operation. This SID
adapter must not be reused as end-user authentication for an HTTP service.

## Startup scope (dev6)

Trusted startup arguments can further restrict a connection:

```powershell
python -m rentgen_core.stdio_mcp --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --allow-tool rentgen_project_head --allow-tool rentgen_source_list
```

`--project` accepts one canonical UUID. Every structured project selector,
including nested SourceRef, proposal and expected head selectors, must match it.
There is no replacement of caller selectors or fallback to another project.
`--allow-tool` may repeat with distinct registered names; only these tools appear
in `tools/list` and execute. A known excluded tool returns `MCP_TOOL_FORBIDDEN`;
a different project returns `MCP_PROJECT_FORBIDDEN`. Checks precede dispatch and
registry/source access. Unknown names still return `UNKNOWN_TOOL`. Requests cannot
set or widen startup scope. Current membership/permission checks remain in force.

Without either option the original 21-tool contract is retained. Project-only
startup exposes the 20 tools with explicit project selectors, excluding
`rentgen_project_list`. Explicitly combining project scope with that registry-wide
tool is a startup error. Tool-only scope may access the SID's authorized projects.
Unknown/duplicate tool names, invalid/repeated project selectors and incompatible
combinations exit with code 2 before runtime initialization. Scope is immutable
for the connection; changing it requires restarting with trusted arguments.

This limits this MCP process, not other processes running as the same Windows
account. It is separate from Cline's UI approval settings and from protected
output permission checks. State schema 4 is unchanged.

## Tool contract

Unrestricted startup exposes twenty-one tools; the previous dev2 artifacts expose ten. All tools return MCP text content containing JSON and equivalent
`structuredContent`. Success uses `{result, request_id}`; operational errors use
the core `{error: {code, message, request_id, details}}` envelope and `isError=true`.
Unknown tools return `UNKNOWN_TOOL`. Schemas reject unknown fields, null or blank
selectors, out-of-range options and numeric type coercion.

Since dev7, schema failures retain `INVALID_ARGUMENT` and add bounded `details`:
`path` is a JSON Pointer (empty string for the root), `rule` identifies the failed
constraint, and expected types/ranges/patterns or allowed/required fields explain
how to correct the request. For example, omitting draft `title` reports
`missing_fields: ["title"]`; a misplaced `manifest_hash` reports it under
`unexpected_fields` and lists the allowed fields for that object. Only names
already declared in published schemas are reflected. Arbitrary field names are
counted as `unrecognized_field_count`; argument values/source text are never
included. This feedback does not weaken validation, startup scope or membership.
Semantic failures after schema validation keep their existing core error codes.

| Tool | Required arguments | Optional arguments |
|---|---|---|
| `rentgen_project_list` | none | none |
| `rentgen_project_head` | `project_id` | none |
| `rentgen_publication_receipt` | `project_id`, `operation_id` | none |
| `rentgen_capture` | `project_id`, `operation_id`, `expected_head` | none |
| `rentgen_source_list` | `project_id`, `snapshot_id` | `limit` (1–200, default 100), `cursor`; development checkout also supports `query`, `kind`, `layer` |
| `rentgen_source_read` | `project_id`, `snapshot_id`, `layer_id`, `relative_path` | none |
| `rentgen_graph_resolve` | `project_id`, `snapshot_id`, `layer_id`, `relative_path` | none |
| `rentgen_impact` | `project_id`, `snapshot_id`, `layer_id`, `relative_path` | `depth` (1–5, default 1) |
| `rentgen_proposal_create` | `project_id`, `snapshot_id`, `source_ref`, `replacement_base64` | none |
| `rentgen_proposal_check` | `project_id`, `snapshot_id`, `proposal`, `diagnostics_profile` | none |

Project and operation IDs are canonical lowercase UUIDs. Snapshot IDs are
lowercase SHA-256 digests. Every source/graph request requires an explicit
snapshot; there is no default/latest fallback. Layer and source paths are the
exact locators returned by `rentgen_source_list`, not display aliases.

The development checkout adds [whole-snapshot source discovery](SOURCE-DISCOVERY.md):
path substring `query`, `kind=all|module`, and exact `layer`, applied before pagination.
Filtered cursors bind all three options; installed dev2 artifacts do not include this change.

Seven [shared draft tools](DRAFT-MCP.md) add save/get/list/history/archive/restore/
receipt through the same core state. They return `result.draft`, use explicit
revision and operation IDs, and preserve history across server sessions. Their
actual SDK response cap is 2 MiB; inline candidates remain bounded to 8 KiB.

Four more [large saved-draft tools](LARGE-DRAFT-MCP.md) start a candidate from an
exact retained source, edit unique text spans, read immutable chunks and check a
saved revision. Complete candidates up to 1 MiB stay in project state; callers
do not resend the whole module. No source apply or platform tests are asserted.

`rentgen_project_list` discloses authorized stable IDs and labels only. Bootstrap,
layer configuration, membership administration and schema migration remain CLI
operations; they are not tools in this server.

`expected_head` is the exact head returned by `rentgen_project_head`:

```json
{
  "project_id": "<registered project UUID>",
  "revision": 0,
  "snapshot": null,
  "source_revision": 1
}
```

For a published head, `snapshot` is its complete
`{project_id, snapshot_id, manifest_hash}` object. The client chooses one operation
UUID and saves it with this head before calling capture. A conflict returns an
error; the server never fetches a new head and silently retries. Repeating an
already committed operation with its original head returns the exact durable
receipt even after a later publication.

Source reads return `ref`, `raw_sha256`, `size_bytes`, `encoding: "base64"` and
`data`. Base64 decodes to the exact captured bytes, including BOM, line endings
and opaque/invalid-UTF-8 payloads. Graph methods return the core pinned
project/snapshot/manifest/capability envelope. Quality remains `unavailable`;
source-path locators do not become verified 1C metadata UUIDs.

## Proposals and real BSL diagnostics

Proposal creation requires `project:read` and `source:edit`; checking also requires
`analysis:run`. Supply the complete `SourceRef` from `rentgen_source_read`, not a
reconstructed path. Proposals bind the original captured bytes and replacement to
one explicit snapshot. Neither tool writes the live source. `proposal_create`
returns a bounded diff; `proposal_check` verifies the original from the same
snapshot and runs the separately installed fixed BSL profile. Results explicitly
say `ephemeral_unattested`, `tests: not_run` and `apply: unavailable`.

Only the documented profile ID is selectable. A tool cannot choose Java, JAR,
working directory, environment or analyzer options. Permissions are checked before
source/runtime IO, throughout the run and at the actual SDK output boundary.
`serve()` installs the guarded stdout writer; integrations using `create_server()`
with their own transport must provide an equivalent final output boundary.
Internal authorization metadata is removed before output. The final check and OS
write are not claimed to be atomic with a concurrent membership transaction.

Installation, CLI equivalents and result interpretation: [PROPOSAL-CHECK.md](PROPOSAL-CHECK.md).

## Limits and lifecycle

- Each input wire frame is at most 64 KiB, including its newline. Invalid UTF-8,
  duplicate JSON keys, non-finite numbers, malformed JSON and larger frames end
  the transport before SDK tool dispatch. Diagnostics go to stderr; stdout
  contains only MCP protocol messages.
- Source responses permit at most 1 MiB of raw bytes. Larger sources return
  `SOURCE_OUTPUT_LIMIT_EXCEEDED`; use local CLI export. The existing core retained
  reader may read up to its capture file limit (64 MiB) to verify the hash before
  the MCP response-size check; the MCP adapter does not expose a private raw file
  reader or weaken verification to avoid this read.
- Each serialized tool result is at most 2 MiB. Larger results return
  `OUTPUT_LIMIT_EXCEEDED`, never a truncated successful result. Text and structured
  content contain the same JSON, so the complete MCP response can be approximately
  twice the result bound plus protocol overhead.
- Proposal tools have stricter limits: 8 KiB replacement, 16 KiB canonical
  proposal, 24 KiB arguments and diff, 128 KiB complete output frame including
  duplicate text/structured content, request ID and newline. Original module
  limit is 1 MiB. Oversize results fail; no partial successful diagnostic is sent.
- One tool worker runs at a time, with at most eight running/queued tool calls.
  Excess calls return `SERVER_BUSY`. SDK initialize/list/ping/cancellation handling
  remains on the event loop and is responsive while capture runs in the worker.
- A queued cancelled request can be discarded before work starts. An already
  started worker is shielded until completion. On client cancellation, the SDK
  returns its protocol cancellation response; that response is **not evidence of
  rollback**. The worker may commit. On stdin EOF, the server waits for an active
  worker before exiting and may be unable to deliver its response.
- Repeated cancellation notifications for an admitted active tool call are
  suppressed before SDK dispatch, so SDK 1.30 emits only one cancellation response
  while its shielded worker finishes. Tracking is limited to the eight admitted
  calls and is released when each handler exits; there is no session-long ID cache.
- After cancellation, disconnect, timeout or lost response, use
  `rentgen_publication_receipt` with the original project/operation ID. If no
  receipt exists and a retry is appropriate, reuse the operation with its
  **original** expected head. `PUBLICATION_OUTCOME_UNKNOWN` remains unknown; it
  never becomes `committed=false`. A client that forcibly terminates the process
  can interrupt it before commit or lose a committed reply; the same durable
  core receipt protocol applies. No automatic garbage collection or orphan
  promotion is performed.

## Evidence and remaining scope

Tests exercise the official SDK client over a real subprocess, actual Go capture,
raw byte fidelity, S1/S2 pinning, revoked membership, concurrent request bounds,
wire rejection, cancellation during a paused real publication, graceful EOF
before/after commit, and process termination after commit followed by replay.
These are tests of this new stdio entrypoint. They do not prove migration of the
two older MCP families, HTTP consumers, enrichers or portal E1–E4. Clean-wheel and
offline installation remain separate packaging gates. Capture temporal atomicity
is `not_proven`; static graph coverage is not full BSL semantic analysis or
release/apply acceptance.

Implementation references: [official SDK low-level server](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/docs/low-level-server.md),
[MCP cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation),
and [AnyIO worker cancellation](https://anyio.readthedocs.io/en/stable/threads.html).
