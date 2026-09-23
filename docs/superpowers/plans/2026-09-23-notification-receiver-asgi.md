# Notification receiver ASGI boundary implementation plan

> **For agentic workers:** Execute this plan inline in small TDD cycles; review
> each committed task before continuing.

**Goal:** Deliver one bounded HTTP ingress to `NotificationReceiver`, prove a
real TLS sender-to-receiver round trip, and preserve the existing digest-only
receipt semantics.

**Architecture:** A dependency-free ASGI callable handles one route and passes
validated headers/body to the existing synchronous receiver in a worker thread.
Uvicorn is a test host only. Startup initialization happens through ASGI
lifespan, and a failed startup never serves requests.

**Tech Stack:** Python 3.11, ASGI HTTP 2.0+ messages, existing SQLite receiver,
pytest/anyio, Uvicorn and cryptography from the locked test environment.

## Global constraints

- Keep the core runtime dependency list empty; ASGI is a protocol callable.
- Accept only exact raw `b"/notifications"`, empty query/root path, POST and
  `scope["scheme"] == "https"`.
- Require one canonical `Content-Length`, reject `Transfer-Encoding`, duplicate
  and malformed ASGI headers; pin a parser that rejects ambiguous wire framing.
  Cap at 64 headers, 128 body chunks and 1,048,576 bytes.
- Do not log or return bearer credentials, body, DB path or exception text.
- Do not install a service or expose a non-loopback socket in tests.
- No production deployment; the receiver still stores only a digest receipt.

## Task 1: Startup and successful request

**Files:** create `rentgen_core/notification_receiver_asgi.py`; create
`tests/unit/test_notification_receiver_asgi.py`.

**Interface:** `NotificationReceiverASGI(receiver: NotificationReceiver, *,
max_body_bytes: int = 65536)` is an ASGI 3 callable. It consumes lifespan
startup/shutdown and HTTP `scope`, `receive`, `send`. It produces fixed empty
responses with `http.response.start` and `http.response.body`.

- [ ] Write a test that constructs a real receiver in `tmp_path`, sends
  `lifespan.startup` and checks `lifespan.startup.complete`; send an HTTPS POST
  scope with raw path `/notifications`, valid body and headers from the existing
  sender contract. Expect 204 and receiver count 1.
- [ ] Run `python -m pytest -q tests/unit/test_notification_receiver_asgi.py`
  and observe import failure for the missing module.
- [ ] Implement only constructor validation, lifespan initialization, exact
  route check, one bounded body read, `asyncio.to_thread(receiver.accept, ...)`
  and fixed empty response.
- [ ] Run the same test until it passes, then add a retry with the same key and
  body. Expect 204 again and count 1; a different body with that key must get
  409 and leave count 1.
- [ ] Run Black, Ruff, the focused tests and `git diff --check`; commit the
  self-contained request path.

## Task 2: Wire and failure boundaries

**Files:** modify the same module and test file.

**Interface:** The app refuses a request before `receiver.accept` unless ASGI
headers and body match the strict design. It returns 400, 404, 405, 413 or 503
with an empty body and fixed headers. A pre-body disconnect sends no response
and commits no receipt.

- [ ] Add table-driven failing tests for duplicate `Authorization`, duplicate
  `Content-Length`, absent/noncanonical `Content-Length`, `Transfer-Encoding`,
  non-ASCII value, wrong path/method/scheme, query, missing raw path, an
  oversized body, a length mismatch and too many body chunks. Assert count 0
  in each case.
- [ ] Add failing tests for malformed `http.request` messages, disconnect before
  completion, receiver unavailable after DB replacement, and failed startup.
  Assert no raw exception text or credentials in every response.
- [ ] Add the smallest validation helpers for raw header pairs and body events;
  keep them private to the ASGI module. Map known receiver storage errors to
  503 without changing `NotificationReceiver`.
- [ ] Run focused tests, Black, Ruff and `git diff --check`; commit.

## Task 3: Real loopback TLS path

**Files:** create `tests/integration/test_notification_receiver_https.py`.

**Interface:** The test starts Uvicorn with a generated self-signed certificate,
`proxy_headers=False`, `access_log=False`, `http="httptools"`, one worker and loopback binding. The
existing `WebhookAdapter` sends a real HTTPS notification using a test trust
context; the receiver persists one digest. Reopen the receiver and repeat the
same key to prove duplicate 204. An HTTP request to the TLS port must not create
a receipt.

- [ ] Write the integration test first. Generate an ephemeral certificate with
  cryptography into `tmp_path`; no private key enters the repository.
- [ ] Run only that test and observe failure before the ASGI app is wired to a
  live server.
- [ ] Connect the app to Uvicorn in the test process or owned child, bound only
  to `127.0.0.1`. Keep startup/teardown bounded and stop only the owned server.
- [ ] Verify accepted/duplicate delivery, TLS validation, no plain-HTTP
  receipt, and an exact SQLite count of 1. Run the focused integration test and
  the receiver/delivery unit tests. Commit.

## Task 4: Document and qualify candidate

**Files:** modify `rentgen_core/__init__.py`,
`docs/product/NOTIFICATION-RECEIVER.md`, `docs/product/READINESS.md` and
release metadata only after the code and tests pass.

- [ ] Export the callable from the core package and document its route, startup,
  wire rules, TLS-host obligations, digest-only guarantee and unsupported cases.
- [ ] Run the full Python, Node and Go checks, installed offline kit verification
  and the real loopback TLS test; record exact source SHA and artifacts.
- [ ] Request independent read-only review of the exact branch diff and fix any
  blockers. Push a PR with evidence; merge only after exact push and PR CI pass.
- [ ] Version and publish the accepted core prerelease with detailed GitHub
  announcement, hashes and explicit limitations. Update the checkpoint and
  verify public `main` and release state. No production deployment.
