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
receipts = deliver_outbox(NotificationOutbox(outbox_path), adapter, limit=25)
for receipt in receipts:
    if receipt.status is DeliveryStatus.RETRYABLE:
        schedule_explicit_retry(receipt.notification_id)
```

The example host and caller functions are placeholders, not installed services.
There is no CLI command, background thread, service registration, implicit
network call from the watcher, or automatic retry loop.

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
must deduplicate the key; the client cannot promise exactly-once delivery.

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
atomic writes and cross-process producer locking remain unchanged. The host
must serialize consumers. Acceptance followed by process death or local ack
failure leaves an event eligible for duplicate delivery; ack errors propagate.

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
The unit tests make no external requests. Live endpoint acceptance, receiver
deduplication, DNS policy and production secret provisioning are not asserted
by these tests.
