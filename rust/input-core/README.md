# Rentgen immutable input core (experimental Linux slice)

This unpublished crate moves submitted-ZIP file acquisition, validation, hashing,
and bounded decoding into Rust. It does not replace Rentgen's XML authorization or
metadata interpretation, the Windows retained-read path, or the Go scanner. It
is not an extractor, generic ZIP service, live project scanner, or release claim.

## Build and test

Use a verified official Rust distribution (qualification used Rust/Cargo 1.92.0)
and the committed Cargo.lock. The manifest minimum is Rust 1.85 because locked
indexmap/hashbrown require it; Rust 1.85 itself has not been qualified here. The
built x86_64 GNU/Linux binary requires glibc 2.34+ and libgcc_s (qualification host:
glibc 2.41), in addition to Linux 5.9+ for close_range. Normal developer commands:

```sh
cargo build --locked --manifest-path rust/input-core/Cargo.toml
cargo test --locked --manifest-path rust/input-core/Cargo.toml -- --test-threads=1
cargo test --locked --manifest-path rust/input-core/Cargo.toml --test sidecar \
  absolute_session_deadline_terminates_partial_frame -- --ignored --exact
```

Set `RENTGEN_INPUT_CORE_TEST_BINARY` to a verified release binary's absolute path
to run the process/lifecycle integration tests against that exact binary. Without
it, Cargo's test-build executable is used.

An offline vendor cache can be configured with Cargo's standard source replacement;
no machine-specific source paths are committed. In memory-constrained builders,
use `-j1` and `RUSTFLAGS='-C codegen-units=1 -C link-arg=-Wl,--threads=1'` with the
Rust-distribution LLD linker. The qualification invocation used a 1 GiB build
address-space ceiling. These compiler limits are separate from the sidecar's
128 MiB runtime ceiling.

`DEPENDENCY_PROVENANCE.json` records exact registry-checksum comparisons and vendor
file-integrity checks for all 42 registry packages. It explicitly distinguishes
those checks from independently downloading/authenticating `.crate` archives.
Zip defaults are disabled; only `deflate-flate2` and flate2's pure Rust
`rust_backend` are enabled. Zip 7.2.0 is outside the affected range of
[RUSTSEC-2025-0168](https://rustsec.org/advisories/RUSTSEC-2025-0168.html), and no
extraction API is used. This is not a claim of a complete dependency audit.

## Ownership and safety boundary

The only executable interface is:

```text
rentgen-input-core --parent-pid <the current invoking Python PID>
```

Linux 5.9+ is required (`close_range` support). Before hello, the sidecar sets
`PR_SET_PDEATHSIG=SIGKILL`, verifies the current parent, closes all inherited file
descriptors above 2, disables dumpability/core dumps, and installs a 128 MiB
`RLIMIT_AS`. It creates no threads or subprocesses and uses no network API. This
is parser/process hardening, not a syscall or filesystem sandbox. Linux's
parent-death signal tracks the thread that created the child, so that spawning
thread must remain alive for the intended session lifetime.

A kernel real-time timer ends the process after an absolute 60 seconds, including
partial-frame reads and blocked response writes. During import, the earlier of
the remaining session deadline and 10 seconds is armed. SIGALRM is reset to its
default terminating disposition and unblocked before use. Internal import loops
also check an `Instant` deadline. EOF closes the process; explicit close is the
only successful exit (status 0). Parent death, timeout and malformed transport
terminate unsuccessfully. A parent must independently wait/reap and verify exit;
a requested signal alone is not proof of termination. Uninterruptible kernel I/O
can delay signals and cannot be made a hard wall-time guarantee by this process.

The startup path must be an absolute trusted locator. It is walked from `/` with
no-follow directory descriptors, then opened exactly once with
`O_NOFOLLOW|O_NONBLOCK`. Dot components, empty components, trailing separators,
symlink ancestors/leaves, special files and files with link count other than one
are rejected. The original leaf descriptor remains owned until close/drop.
Archive bytes are read once into bounded private memory, with before/after
size/device/inode/mode/link-count/mtime/ctime comparison. Validation then operates
only on those bytes and never reopens a path. Accepted decoded file buffers are
immutable and addressed by numeric IDs.

These are local-filesystem semantics. Network, FUSE and unusual filesystems may
have weaker metadata or I/O guarantees. A matching SHA-256 establishes byte
equality with the caller's expected hash; it does not prove source identity,
authorize a project, freeze a live file, or establish who supplied the hash.
Accepted session bytes remain immutable even if the source is changed/replaced
later. No customer archive or decoded source content is logged to stderr.

## Narrow accepted ZIP profile

Hard limits:

- 16 MiB compressed archive; 4,096 central-directory members
- 4 MiB decoded per file; 32 MiB total decoded files
- 1,024 bytes per archive name; 4,096 bytes per startup locator
- 65,536-byte JSON frames; 32 metadata entries/page; 32,768-byte read chunk

Before constructing `ZipArchive`, a bounded ZIP32 central-directory preflight
checks count, record extents and metadata limits. Then every member is parsed and
fully decoded with the maintained `zip` library, with actual length/CRC checks,
before the open response can succeed. A separate bounded raw-Deflate check
requires explicit StreamEnd, exact decoded size and consumption of the complete
compressed member range, rejecting truncated streams and trailing compressed junk. Stored and Deflate are the only supported
methods. ZIP32 data descriptors (with/without signature) are supported.

Rejected: ZIP64, multidisk, encryption, unsupported flags/methods, special/symlink
members, invalid UTF-8 names, alternate Unicode-path extras, unsafe path
components (including portable invalid characters and Windows device names in
files and directory-only members), repeated names, NFC/casefold aliases (including implicit directories),
file/directory conflicts, local/central disagreement, overlapping members,
unreferenced records, prepended stubs, inter-record gaps, trailing data, malformed
extra fields, size/CRC failures and budget overflow. Canonical alias-key storage
is linear in the submitted path bytes; deep paths do not allocate every prefix.
Directory entries must be empty Stored members. The EOCD must be the final 22
bytes, with an empty archive comment, and no earlier `PK\x05\x06` byte signature
may occur anywhere in the archive. This conservative restriction can reject an
otherwise valid ZIP containing those bytes in compressed data or a member. It
prevents the general-purpose parser's fallback EOCD search from selecting
unchecked metadata and allocating from an unchecked count. The parser is also
configured with a fixed zero archive offset.

The archive root is always the root. A guessed wrapping folder is never stripped.
Files-only metadata is exposed in central-directory order with sequential IDs;
validated directory members contribute to `entries_count` but not `files_count`.
Unsupported export layouts remain the Python metadata layer's responsibility.

## Protocol v1

See [PROTOCOL.md](PROTOCOL.md). The parent must pin the executable, validate every
response and SHA-256, enforce its own byte/deadline bounds, and confirm child exit
before releasing a successful overall result. Runtime caps alone do not make an
unverified executable trusted.
