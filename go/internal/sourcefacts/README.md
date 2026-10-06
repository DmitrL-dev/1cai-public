# Submitted-source lexical scanner (experimental Linux slice)

`cmd/bsl-source-facts` is a separate one-shot executable. It does not alter
`bsl-scan`, its scanner modes, legacy extraction, or call graph outputs.
The authoritative byte/grammar contract is
[`SOURCE-FACTS-PROTOCOL.md`](../../../docs/product/SOURCE-FACTS-PROTOCOL.md),
SHA-256 `ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.

This package consumes only the two explicitly submitted byte buffers (or one
same-entry alias) and a raw-byte selection. It can observe a qualified-looking
lexical selector and a matching candidate header's Export marker. It cannot
establish receiver binding, namespace membership, BSL semantic validity,
accessibility, runtime behavior, method absence, or native 1C correctness.
No file paths, XML, query, expected labels, or stronger binding override are
accepted. Source strings and identifier copies never appear in its response.

## Components

- `wire.go`: bounded, object-only JSON validation, duplicate decoded keys,
  scalar-safe escaped strings, integer lexemes, exact variant schemas,
  canonical padded base64, entry identity, size and raw SHA-256 checks.
- `lexer.go`: independent strict whole-buffer UTF-8/BOM/control/line checks,
  the frozen small token alphabet and exact identifier case mapping.
- `headers.go`: single-line lexical headers, explicit reserved-name guard,
  duplicate/limit checks, routine ownership and balanced body delimiters.
- `scan.go`: exact selected token extent, predecessor/trailing-chain guards,
  independent role admission and span-only/closed-value serialization.
- `framing.go`: one hello, one bounded request requiring EOF, one response.
- `cmd/bsl-source-facts`: exact `--parent-pid UINT` CLI; locked ownership
  goroutine, Linux PR_SET/GET_PDEATHSIG SIGKILL and post-install parent race
  check; verified RLIMIT_CORE zero; no source filesystem or network access.

The only unsafe operation is the fixed-size integer output pointer passed to
Linux PR_GET_PDEATHSIG. The executable does not close arbitrary descriptors
owned by the Go runtime. Its launcher must close inheritance except stdio and
the sealed executable descriptor and keep the actual launching thread alive.
Non-Linux builds fail closed before hello; no weaker ownership is advertised.

## Resource boundaries

Input frames are capped before payload allocation. Each raw source is capped at
524,288 bytes; the request allows 1,500,000 JSON bytes for two canonical base64
buffers. Token, identifier, literal/comment, routine, parameter and delimiter
caps are independent. JSON containers are limited to depth 12, and arrays are
rejected. No subprocesses, source file reads, or network operations are present
in the executable or package.

The executable uses GOMAXPROCS(1), a 64 MiB Go runtime soft memory target, and a
10-second fail-closed watchdog covering blocked streams as well as parse work.
The soft target is **not** a hard RSS limit or sandbox. No RLIMIT_AS is applied:
Go's virtual memory reservations differ from the existing Rust input-core.
The parent must separately enforce the frozen handshake, exchange and overall
monotonic deadlines, cap/discard stderr, kill only owned processes on failure,
and confirm exit and reap before disclosing any result. Measured RSS and actual
ownership/process regression results are required acceptance evidence.

## Development verification

The source-authored tests use only handwritten development buffers. They cover
closed admission reasons and limits, selectors, mixed RU/EN headers, aliasing,
source preservation, privacy canaries, strict JSON/base64/hashes, framed EOF,
partial/trailing messages, pre-hello setup failures, and Linux parent death.
Parent-death tests use disposable subprocess helpers and a test-only subreaper
to verify actual SIGKILL and reap the exact child; production never launches
children or becomes a subreaper.

After the coordinated source freeze, use the pinned Go 1.25.5 toolchain and one
build job, e.g. `GOMAXPROCS=1 go test -p 1 ./internal/sourcefacts ./cmd/bsl-source-facts`
from `go/`. Actual binary integration and legacy regression runs are separate
acceptance stages. No passed count or withheld-fixture qualification is implied
by the presence of these development tests.
