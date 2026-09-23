# Durable notification receiver core

`rentgen_core.notification_receiver.NotificationReceiver` is the bounded
receiver-side contract for the Git watcher outbox. It accepts the existing JSON
notification envelope only after checking a configured bearer token, an exact
lowercase SHA-256 `Idempotency-Key`, the JSON content type and a UTF-8 body limit.
The receiver stores the idempotency key, canonical payload digest and receipt
timestamp in an owned SQLite database; it never persists the request body or
credentials. `NotificationReceiver`, `ReceiverResult` and `ReceiverStatus` are
also exported from `rentgen_core`.

```python
from rentgen_core import NotificationReceiver

receiver = NotificationReceiver(
    r"C:\Rentgen\receiver\receipts.sqlite3",
    bearer_token=token,
    max_body_bytes=65536,
)
receiver.initialize()
result = receiver.accept(headers, body)
```

The host owns the HTTP boundary and maps `ReceiverResult.http_status` to its
response. The core does not open a socket, start a thread, register a service or
infer a network policy. The host must enforce its method/routing/framing rules,
reject duplicate wire headers before converting them to a mapping, bound and
read the request body before passing it to `accept`, avoid logging request
headers/body, and provide TLS and endpoint access control. Startup initialization
must finish before serving requests; initialization and filesystem recovery are
serialized by the host.

The accepted header subset is a mapping of at most 64 ASCII fields, with HTTP
token names of at most 128 characters and nonempty values of at most 8192
characters. Names are case-insensitive; duplicate names, controls and non-ASCII
values are rejected. Authorization is exactly `Bearer <configured-token>`;
the token is 1–4096 characters including any trailing `=` padding. Content type
is `application/json`, optionally followed by `; charset=utf-8` (case-insensitive).
Other parameters are rejected. The body must be `bytes`, strict UTF-8, and fit
the configured limit of 1–1,048,576 bytes.

The payload uses the delivery adapter's existing `{id, event, created_at}`
envelope. Extra fields, duplicate JSON members at any depth, nonfinite numbers,
invalid Unicode, excessive nesting and timezone-free timestamps are rejected.
The digest covers the full envelope, serialized with the same sorted-key,
compact UTF-8 JSON rules as the sender. Formatting and key order do not change
the digest. Timestamp strings and JSON number types are preserved by these
rules; this is not a general semantic JSON or timestamp normalization standard.

The first request for a key commits one digest and returns `accepted`/204. A
retry with the same key and canonically equivalent envelope returns
`duplicate`/204. Reusing a key for a different envelope returns
`conflict`/409 and does not alter the stored receipt. Invalid credentials,
headers, content type, JSON or size return `rejected` with 400, 401 or 413 and
never write receipts. SQLite's unique key and `BEGIN IMMEDIATE` transaction
serialize concurrent retries, including independent receiver instances: one
request commits and the others observe a duplicate or conflict after the commit.
Contention can instead reach the five-second SQLite busy timeout and fail closed;
the timeout is a lock-wait setting, not a total request deadline.

The store is schema-versioned and bounded to 100,000 receipts. Exact table/index
definitions, schema version and every receipt's key/digest/UTC timestamp are
validated in the same transaction on initialization, `count()` and every valid
request, including duplicates. Unknown tables, indexes, triggers, views,
malformed receipts and changed journal mode fail closed. This full validation
cost grows with the receipt count; throughput at capacity is not qualified.
At exactly the receipt limit, existing keys still return duplicate/conflict;
new keys fail. If the store already exceeds the limit, every valid request fails.
There is no automatic eviction or reset, which would lose deduplication history.

Each existing database or SQLite sidecar file is capped at 64 MiB before opening;
individual SQLite values/rows and SQL statements are capped at 8192 bytes.
Connections use existing-file mode, DELETE journaling and `synchronous=EXTRA`,
and are always closed. Missing state is never silently recreated by `accept()`
or `count()`. Existing empty or malformed files require explicit recovery;
`initialize()` does not repair or replace them. A failed initialization leaves
the instance unavailable until initialization succeeds again.

The absolute database path, its parents and SQLite `-journal`, `-wal`, `-shm`
siblings must be host-owned on a local filesystem. Static symlinks, Windows
reparse points/junctions, file hardlinks, non-file leaves and ambiguous Windows
names/streams are rejected. The host must protect the directory and sidecar
namespace with permissions, prevent concurrent external replacement, and retain
the database while keys may be retried. These checks do not pin filesystem
identities through SQLite calls or authenticate a valid-looking replaced store.
Network filesystems, hostile concurrent filesystem mutation and restoration of
an older backup are outside this contract.

Storage/configuration failures raise `CoreError`, rather than returning a
`ReceiverResult`: `NOTIFICATION_RECEIVER_INVALID`, `NOTIFICATION_RECEIVER_NOT_INITIALIZED`,
`NOTIFICATION_RECEIVER_CONFLICT` (unsafe path),
`NOTIFICATION_RECEIVER_RECOVERY_REQUIRED` (invalid state),
`NOTIFICATION_RECEIVER_LIMIT`, or `NOTIFICATION_RECEIVER_UNAVAILABLE` (including
busy state and failed/uncertain commits). The host must never turn these errors
into 2xx; unavailable state should be retryable, with fixed diagnostics and no
raw exception chains in HTTP responses. A retry after an uncertain commit safely
discovers whether the receipt was persisted. The immutable result contains only
status, fixed code, HTTP status and optional validated key/digest.

Local tests cover malformed requests/state, linked paths, concurrent retries
and conflicts, commit failures before/after commit, and an injected
outbox → sender → receiver round trip with a lost response followed by reopening
the database. The outbox remains pending after that lost response and is
acknowledged only after the repeated request receives 204. No external requests
are made.

This core acknowledges durable **digest receipt**, and does not store a
recoverable event, run a handler or couple downstream effects to the transaction.
Exactly-once business processing is therefore not provided. Live HTTPS
socket/TLS/DNS acceptance, production secret provisioning, SCM deployment,
hard process termination and power-loss testing remain unaccepted. SQLite's
[EXTRA durability mode](https://www.sqlite.org/pragma.html#pragma_synchronous)
still depends on the host filesystem and storage honoring synchronization.
