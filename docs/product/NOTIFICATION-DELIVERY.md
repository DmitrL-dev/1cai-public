# Explicit HTTPS notification delivery

`rentgen_core.notification_delivery` delivers events already persisted in
`NotificationOutbox`. Importing or constructing the adapter does not connect to
the network. The caller explicitly invokes one bounded foreground batch:

```python
from rentgen_core import DeliveryStatus, WebhookAdapter, deliver_outbox
from rentgen_core.git_watcher import NotificationOutbox

# Supply the token from the host's in-memory secret provider.
adapter = WebhookAdapter(
    "https://notifications.example.org/rentgen",
    allowed_hosts={"notifications.example.org"},
    namespace="production-project-a",  # Stable and unique per outbox generation.
    bearer_token=token,
    timeout=10,
    max_payload_bytes=65536,
    max_response_bytes=4096,
)
receipts = deliver_outbox(
    NotificationOutbox(outbox_path), adapter, limit=25,
    authorize=check_current_permissions,  # raises when access was revoked
)
for receipt in receipts:
    if receipt.status is DeliveryStatus.RETRYABLE:
        schedule_explicit_retry(receipt.notification_id)
```

The example endpoint and caller functions are placeholders, not installed services.
There is no CLI command, background thread, service registration or implicit
network call from the watcher. Current source has an explicitly started foreground
host described below; constructing it does not start delivery.

`authorize` is required. It runs before every send and again before every ack;
a refusal stops the batch, and the current event stays pending. Delivery never
assumes a permission that was valid when the batch started.

## Wire contract and outcomes

The adapter sends one JSON POST containing the existing outbox envelope:
`{"id": 1, "event": {"status": "analyzed"}, "created_at": "...+00:00"}`.
Notification IDs are strict integers in `1..2**63-1`; booleans are invalid.
The event remains a JSON object, so existing watcher status/error/receipt events
do not require a new event ID. Keys must be strings, nesting is limited to 64,
and non-JSON values, nonfinite numbers and timezone-free timestamps fail closed.

`Idempotency-Key` is SHA-256 of
`rentgen-notification-v1:{namespace}:{notification_id}`. Keep the namespace stable
across retries and unique across independent queues. When an outbox is deleted
and recreated with IDs restarting at one, assign a new namespace. The receiver
must deduplicate the key; the client cannot promise exactly-once delivery. The
bounded receiver-side contract is documented in
[`NOTIFICATION-RECEIVER.md`](NOTIFICATION-RECEIVER.md); it stores only a
canonical payload digest and rejects conflicting key reuse. Its 204 confirms a
durable digest receipt; the core neither retains a recoverable event nor executes
downstream business effects.

`DeliveryResult` is immutable and contains only status, validated notification
ID, idempotency key, fixed diagnostic code and optional HTTP status. It contains
no endpoint, headers, response body, exception text or bearer token.

| Result status | Meaning | Queue action |
| --- | --- | --- |
| `accepted` | HTTP 200..299 with a valid bounded response | `ack(id)` |
| `retryable` | Transport/HTTP protocol failure or HTTP 500..599 | Remains pending |
| `permanent` | HTTP 1xx/3xx/4xx, malformed response or invalid payload | Remains pending for operator decision |

HTTP 429 is classified with other 4xx as permanent; no `Retry-After` scheduling
is inferred. A response exceeding its limit is permanent even when its status
is 2xx. Every selected event receives at most one attempt per invocation, and
later events are still attempted after an earlier rejection. There are no blind
retries. A constructor configuration error raises the sanitized
`NOTIFICATION_DELIVERY_INVALID` CoreError before network access.

The batch reads and validates the entire bounded queue before making the first
request, then attempts at most `limit` events (`1..1000`, default 100). A malformed
queue raises CoreError with no delivery or acknowledgement. Existing outbox
atomic writes and cross-process producer exclusion remain in place. Windows
acquires the outbox byte lock before initializing its byte, including an empty
lock file. A competing holder reaches the bounded lock acquisition loop and
`GIT_WATCHER_NOTIFICATION_BUSY` instead of an unguarded read raising
`PermissionError`. No queue bytes are read or written before acquisition. The host
must serialize consumers. Acceptance followed by process death or local ack
failure leaves an event eligible for duplicate delivery; ack errors propagate.

## Durable retry journal in current sources

An explicit `DeliveryJournal(path, namespace=adapter_namespace)` can be passed
as `journal=` together with `retry_policy=RetryPolicy(...)`. The host still
invokes each batch, directly or through the foreground host; no background
thread or implicit network call is added. All
consumers of one outbox generation must share that journal and namespace.
Do not mix journaled delivery with legacy consumers or independent journals.

The journal lock serializes consumers before they read the queue. The whole
bounded queue is validated before sending; a waiting consumer cannot reconcile
against a stale queue and discard another consumer's attempt. Each attempt is
persisted before transport. Retryable outcomes wait
`min(max_delay_seconds, base_delay_seconds * 2 ** (attempt - 1))`: defaults are
8 attempts, 30 seconds initial delay and 3600 seconds maximum. Bounds are
1–100 attempts and 1–86400 seconds, with maximum delay at least the base delay.
There is no jitter or inferred `Retry-After` support.

Permanent responses and exhausted retries become terminal but remain in the
outbox. They need the host's explicit operator decision; `journal.rearm(id)`
grants a fresh bounded attempt budget without changing the payload binding or
idempotency key. Lowering the policy never grants extra attempts. A trusted
host clock controls due times; a rollback exceeding the maximum delay makes a
pending attempt due rather than delaying it indefinitely.

An interrupted `sending` attempt becomes `OUTCOME_UNKNOWN` and consumes its
attempt budget. It may have reached the receiver, which must deduplicate the
same key on retry. Once acceptance is durably recorded, an interrupted ack is
recovered without sending again (`ACK_RECOVERED`). Loss before the acceptance
record can still cause a duplicate. Authorization is checked before every send
and ack, including recovered acks. This does not provide exactly-once delivery.

The journal keeps bounded IDs, payload hashes, attempt counts, fixed error
codes and times; it omits event bodies, endpoint, headers, token and response.
`DeliveryResult.attempt` and `next_attempt_at` expose the attempt and next due
time. `journal.records()` is a private host view. The JSON file is limited to
1 MiB and 1000 entries; reads detect overflow after at most limit + 1 bytes.
Changed payloads, reused acknowledged IDs and another namespace are refused.
Malformed files or a leftover `.tmp` require operator recovery and never
trigger a send. Files and lock directories must be host-owned and protected;
the journal is not a tamper-proof or cross-account authorization boundary.

Tests use an injected transport and real local files. They cover backoff,
reopen, revocation, ack loss, a controlled concurrent-consumer interleaving,
OS-lock exclusion and a real child process exiting inside transport after the
attempt write. They also pin an interrupted last allowed attempt becoming
terminal `OUTCOME_UNKNOWN` until explicit rearm, lowered-policy terminalization,
a clock rollback beyond the maximum delay making a pending retry due, and a
changed payload after durable acceptance conflicting before ack. These are source
contracts, not live endpoint or power-loss qualification.

## Explicit foreground host in current sources

`NotificationDeliveryHost(outbox, adapter, authorize=..., journal=...)` schedules
the existing journaled batches. The journal is required and must use the
adapter's namespace; queue, journal and their `.lock`/`.tmp` paths must not
overlap. Construction performs no send, queue read or journal write. `run()`
runs on the calling thread once and returns the number of completed batches.
Defaults are one batch, 100 selected events and a 30-second interval. Bounds:
`max_cycles=1..10000`, `batch_limit=1..1000`, `interval_seconds=5..86400`;
booleans and an unbounded cycle count are rejected.

The interval is a delay after a completed batch, not a fixed-rate promise.
The journal remains the authority for retry due times, attempt exhaustion,
terminal records and explicit rearm. A pending retry can run on the first
scheduled batch after its due time. Empty/not-due batches still count toward
the finite cycle budget. `last_results` holds only the last completed batch,
bounded by `batch_limit`; it is not an audit log or proof of an empty queue.
An interrupted batch can have durable effects even when its receipts were not
returned. Inspect the journal before recovery.

`stop()` wakes interval waits and is checked before each batch, send and ack.
The host also rechecks current authorization before reading/reconciling an idle
batch. Authorization/storage errors propagate and end the host; they are not
transport retries. An active sender must return before stop takes effect.
If a successful response is persisted before stop prevents ack, a new host
using the same journal recovers the ack without resending. This does not add
a hard transport deadline or an exactly-once guarantee.

The existing Windows `GitAuditWorker` exposes an explicit `notification_host`
factory for schema 2/3 in `read-only` mode. It binds the worker's existing
`git-outbox.json`, fixed `notification-delivery.json` in the Observer profile,
current project authorization and lifetime. No endpoint or credential is added
to service JSON. The embedding host supplies the configured adapter and secret:

```python
from threading import Event
from rentgen_core.service_composition import GitAuditWorker
from rentgen_core.service_entry import load_config

# Existing schema 2/3 read-only config; set max_cycles=1 for this foreground job.
worker = GitAuditWorker(load_config(config_path))
try:
    worker.run(Event())                 # Audit only: never sends notifications.
    delivery = worker.notification_host(adapter, max_cycles=3)
    completed_batches = delivery.run()  # Explicit network operation.
    receipts = delivery.last_results
finally:
    worker.close()                     # Also stops the configured delivery host.
```

Only one delivery host can be composed per worker lifetime. Closing the worker
stops it; restart creates a new worker/host with the same journal and namespace.
An embedding host that runs delivery on its own thread must stop and join that
thread; `close()` does not forcibly terminate an in-flight sender. The normal
`rentgen-service` console/SCM entrypoint remains audit-only. Installed SCM delivery,
production endpoint/secret provisioning and live TLS/DNS acceptance remain separate.

`test_notification_host.py` uses real queue/journal files and an injected sender
for scheduling, stop, concurrency, retry/rearm and ack recovery.
`test_service_notification_host.py` checks real service bindings and project
revocation; its events are fixtures and POSIX substitutes only the Windows lease.
`test_service_notification_capture.py` separately covers real Windows capture,
Git analysis, owner-report event creation and restart/ack recovery with injected
BSL/HTTPS adapters. These tests do not qualify native SCM delivery, 1C or power loss.

## Bounds and credential handling

HTTPS is mandatory. An endpoint must match one of at most 100 exact lowercase
ASCII DNS names in `allowed_hosts`; wildcard/suffix matching is unsupported.
An explicit valid port is allowed. URL credentials, query strings, fragments,
control characters, backslashes and URLs containing the bearer token (including
percent-decoded form) are rejected. Allowlisting authorizes the configured host;
it does not pin DNS addresses or block private networks for an allowed host.

The standard-library urllib transport uses certificate verification and a fresh
opener with redirects and environment proxies disabled. Credentials are provided
only through the optional `Authorization: Bearer ...` header and retained in
memory. The adapter writes no files or logs and never includes transport error
details or response content in receipts. Host code must protect the token and
avoid logging request objects or introspecting adapter internals.

| Bound | Default | Allowed range |
| --- | --- | --- |
| Socket timeout, seconds | 10 | 0.1..30 |
| Request payload, UTF-8 bytes | 65,536 | 1..1,048,576 |
| Response body, bytes | 4,096 | 1..65,536 |
| Endpoint length, ASCII characters | — | 1..2,048 |
| Namespace length | — | 1..128, ASCII letters/digits/`_.-` |

The response read requests at most its byte limit plus one byte to detect
overflow; the response is always closed. urllib's timeout applies to socket
operations, not a hard end-to-end deadline for DNS resolution or a peer that
keeps sending small chunks. Hosts requiring a strict wall-clock deadline must
provide a trusted transport with that guarantee or isolate the worker process.

Tests inject `sender(request, timeout=...)`, returning a closable response with
integer `status` and `read(n)`. This transport is a trusted extension point and
must preserve HTTPS, no redirects, bounded reads and credential handling itself.
The unit tests make no external requests. Receiver core tests cover durable
deduplication, concurrent retries/conflicts, fail-closed storage and an injected
outbox round trip that loses the first response after commit, reopens the receiver
and acknowledges the duplicate on retry. Live endpoint/TLS/DNS acceptance,
production secret provisioning, hard process termination, power loss and
exactly-once downstream processing are not asserted by these tests.
