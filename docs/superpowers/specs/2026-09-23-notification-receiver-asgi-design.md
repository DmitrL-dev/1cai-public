# Notification receiver ASGI boundary design

## Decision and scope

The receiver already authenticates and durably deduplicates an outbox envelope,
but no HTTP request can reach it. This slice adds one dependency-free ASGI 3
application, then proves an installed sender can reach it over a real loopback
TLS connection. It does not install a service or expose a production endpoint.

Three approaches were considered:

1. **ASGI boundary with a separate TLS server (chosen).** ASGI forwards a list
   of headers and streams body chunks, so the adapter can enforce limits on
   what the parser passes before calling the existing core. A real Uvicorn TLS round trip proves
   transport compatibility without coupling the core wheel to a web server.
2. A direct `http.server` host would combine HTTP parsing, socket lifecycle,
   TLS and storage in one new module. This gives less control over the reviewed
   boundary and is harder to test without a host process.
3. A complete packaged receiver service would additionally need certificate,
   secret, account, DNS and Windows service policies. Those host-specific
   decisions require a separate acceptance slice after the request contract is
   stable.

The wire rules below follow the [ASGI HTTP specification](https://asgi.readthedocs.io/en/latest/specs/www.html):
the ASGI header list can retain duplicates, `raw_path` is optional, body events
are streamed, and the protocol server decodes chunked transfer. A parser may
normalize headers before ASGI. The qualified test host therefore pins
Uvicorn/httptools and uses [Uvicorn's documented TLS, HTTP parser and proxy
settings](https://www.uvicorn.org/settings/).

## Public interface

`NotificationReceiverASGI(receiver, max_body_bytes=65536)` accepts a configured
`NotificationReceiver` instance. The ASGI application implements lifespan
startup and shutdown. Startup invokes `receiver.initialize()` before the first
request; a failure emits `lifespan.startup.failed` with a fixed message and
leaves HTTP requests unavailable. The app does not open sockets or read secrets.

One HTTP route is accepted: exact raw path `b"/notifications"`, empty query,
empty `root_path`, method `POST`, and scheme `https`. Missing `raw_path` is
rejected to avoid accepting an encoded alias of the route. The server must
provide real TLS and must not trust arbitrary forwarded scheme headers. A
non-HTTP scope other than lifespan is rejected; WebSocket is never accepted.

The sender's normal request has one `Content-Length` with canonical decimal
syntax, no `Transfer-Encoding`, a body of 1..`max_body_bytes` bytes and at most
128 `http.request` chunks. Body length must equal `Content-Length`. Duplicate
ASGI headers, non-ASCII header values, malformed ASGI events, oversized bodies
and incomplete bodies are refused before `receiver.accept()`. A disconnect
before the complete body creates no receipt. The adapter retains neither body
nor credentials after the request.

The adapter passes validated ASGI headers and body to `receiver.accept()` in a
worker thread, preserving the core's authentication, canonical JSON and SQLite
transaction rules. Accepted and duplicate receipts return 204; conflicting
reuse returns 409; core request errors keep their 400/401/413 status. Storage
and readiness failures return 503. Other routes return 404 and other methods
return 405. Every response has an empty body and fixed headers only; no token,
request body, raw exception or path appears in it. A lost response after commit
can be retried with the same idempotency key and yields duplicate 204.

## Verification and limits

Contract tests drive a real `NotificationReceiver` through ASGI events. They
cover accepted/duplicate/conflict, duplicate headers, route and method,
content-length and body bounds, disconnect, storage failure and startup failure.
A separate loopback test uses Uvicorn/httptools with a generated self-signed
certificate, proxy headers and access log disabled, then sends with the existing
`WebhookAdapter`; it checks TLS verification, durable retry after reconnect,
no receipt from plain HTTP and raw TLS ambiguous-header rejection. No external
address is contacted.

The receiver still stores only a payload digest. This slice does not retain a
recoverable event or provide downstream processing, public TLS certificate
provisioning, DNS policy, an installed service, hostile filesystem mutation
acceptance or production deployment. The existing Windows x64 / Python 3.11
core release remains unchanged until a separately versioned candidate passes
the normal release gates.
