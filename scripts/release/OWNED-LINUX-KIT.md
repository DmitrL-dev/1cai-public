# Candidate: owned Linux CLI + official MCP SDK

`prepare_owned_linux.py` prepares the separate versioned profile
`owned-linux-cli-mcp-py311-x86_64-v1`. It does not modify the accepted dev19
experimental supplement, release schemas, accepted records, tags or assets.
Its output is always `candidate:true`, `accepted:false`, `published:false`,
`linux_installed_cli_mcp_qualified:false`, `full_product_ready:false`.

The target is GNU/Linux x86_64, CPython 3.11.15, glibc >= 2.34 and kernel >= 5.9
with memfd seals, `/proc/self/fd` and `libgcc_s.so.1`. Python and OS libraries
are prerequisites. The official MCP SDK is pinned to 1.30.0 with the separate
[Linux dependency lock](../../requirements/locks/LINUX-MCP-LOCK.md).
The exporter needs Python 3.11 and `packaging` in its build environment. The
selected dependency markers are evaluated for exactly 3.11.15; other patch
versions require their own validation. It
inspects original binary wheels; it never installs packages or runs the
delivered Go/Rust executables while building.

## Trusted inputs

Select the exact full source commit and tree. Read all three product package
inventories (`rentgen_core`, `rentgen_graph`, `rentgen_diagnostics`) from Git;
every wheel product byte must match those blobs. The source also supplies
MIT/Rust notices, the Linux SDK lock/provenance and its bounded dependency
checker. Local uncommitted product files cannot substitute for selected blobs.

Create an input JSON with exactly these fields; the digest/size placeholders
must come from separately verified artifact bytes, not an untrusted replacement:

```json
{
  "schema": 1,
  "profile": "owned-linux-cli-mcp-py311-x86_64-v1",
  "version": "0.1.0.dev19",
  "source_commit": "EXACT_40_LOWERCASE_HEX_COMMIT",
  "source_tree": "EXACT_40_LOWERCASE_HEX_TREE",
  "wheel": {"asset": "rentgen_core-0.1.0.dev19-py3-none-any.whl", "sha256": "TRUSTED_SHA256", "size_bytes": 1},
  "scanner": {"asset": "bsl-scan-owned-linux", "sha256": "TRUSTED_SHA256", "size_bytes": 1},
  "scanner_license": {"asset": "GO-LICENSE", "sha256": "911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad", "size_bytes": 1453},
  "scanner_provenance": {"asset": "go-scanner-build-inputs.json", "sha256": "TRUSTED_SHA256", "size_bytes": 1},
  "rust_helper": {"asset": "rentgen-input-core", "sha256": "TRUSTED_SHA256", "size_bytes": 1}
}
```

The version is read from the selected source's `pyproject.toml`; the example
does not accept or publish a new dev19 asset. A future delivery requires its
own version decision and qualification. Paths supplied by CLI are local input
locations and need not use the logical asset basenames in this JSON.

The scanner observation schema is
`rentgen-owned-linux-scanner-build-observation/1`. It must bind the selected
source commit/tree and exact `go/go.mod` + all tracked `go/**/*.go` hashes,
protocol `rentgen-owned-scanner-linux-v1`, exact source Go version and Linux
amd64 build, Go executable hash, `cgo_enabled:false`, build arguments
`["build", "-trimpath", "-buildmode=exe", "./cmd/bsl-scan"]`, scanner hash/size,
and license path/hash/size (`licenses/GO-LICENSE`). Its scope is exactly
`CI build observation; installed acceptance is a separate receipt`.
This is an explicitly trusted build observation, not authenticated execution
proof or a claim that an official Go archive was independently verified.
The exporter also inspects ELF64/x86_64 headers and rejects dynamic/PIE Go
scanners. It accepts the separately trusted existing Rust helper plus its
unchanged selected-source license and dependency-provenance materials.

From a trusted POSIX build host, with selected source blobs available in Git:

```sh
python3.11 scripts/release/prepare_owned_linux.py build \
  --inputs INPUTS.json --inputs-sha256 TRUSTED_INPUTS_SHA256 \
  --wheel CORE.whl --scanner OWNED_SCANNER \
  --scanner-license GO_LICENSE --scanner-provenance GO_SCANNER_PROVENANCE.json \
  --rust-helper RUST_HELPER --wheelhouse LOCKED_SDK_WHEELHOUSE \
  --output NEW_OUTPUT_DIRECTORY
```

All input hashes and sizes are checked before ZIP interpretation. Each input
is read once into owned bytes through retained no-follow directory descriptors,
with pre/open/post identity checks. Symlinks, hardlinks, pathname traversal,
duplicate/case-ambiguous ZIP names, special members, unexpected wheel versions,
wrong Linux ABI, unlisted dependencies and extra wheelhouse files are refused.
The owned temporary SDK copies are checked against the selected source lock,
metadata, target markers and activated extras without network access. This
guards pathname replacement and detects mutation; it does not isolate a build
from hostile processes with the builder's UID.

The fresh output contains only the deterministic `.tar.gz`, versioned manifest
and checksums. The manifest inventories every final archive file with its hash,
size and mode. Payload and original input budgets remain bounded to 128 MiB
overall and 64 MiB per input; SDK wheels have the checker’s tighter limits.
No local absolute paths, identity state, profiles, credentials or source fixture
contents enter the public build receipt. Original Python license texts remain
inside their unmodified wheels and are also copied under `licenses/python`.
Go and Rust notices/provenance are delivered separately.

## Qualification still required

Build output is a candidate contract, not a statement that installation passed.
The actual scoped result belongs to the separate `acceptance.json` produced by
`verify_owned_linux_delivery.py`. In CI its copy is named
`owned-linux-acceptance.json`, alongside the candidate `.tar.gz`,
`owned-linux-manifest-v1.json` and `owned-linux-SHA256SUMS`: exactly four files
in artifact `owned-linux-cli-mcp-py311-x86_64-v1`. Select the exact workflow run
and source commit/tree; verify the original artifact size/digest before bounded
extraction, then check the receipt against the archive/manifest hashes and sizes,
Core wheel/input inventory, Go/Rust hashes, SDK lock/provenance and all 29 wheels.
The receipt must show CPython 3.11.15 on actual GNU/Linux x86_64, successful local
offline install/`pip check`, installed CLI evidence and `sdk.accepted:true`.
File presence, exporter success and PR #102 source SDK tests are insufficient.
The build manifest keeps all five candidate flags above unchanged even after a
positive separate receipt; neither file authorizes publication or a release.

The [first CI for HEAD `5f7522b`](../../docs/product/evidence/development-ci-5f7522b-20261016.json)
failed before the installed SDK phase: that phase was NOT_RUN and no new owned-kit
artifact was produced. This dated failure remains evidence for those exact bytes;
a later source/run needs its own verified receipt and does not rewrite it.

The generated `INSTALL.md` creates a fresh environment, installs the SDK with
`--no-index --require-hashes --only-binary=:all:`, installs the exact Core wheel
with its hash and runs `pip check`. These instructions must be executed against
the extracted final archive on the actual Linux target. Fresh installed CLI
and official-SDK MCP processes must then demonstrate private default-base
capture, source/graph reads, historical reads and receipt replay, including
stale-operation and wrong-scanner rejection. A synthetic packaging fixture or
successful macOS exporter run does not supply that evidence.

Default capture budgets are 64 MiB total source, 16 MiB per file and 4096 source
entries. This profile does not qualify the larger full-product budgets,
Companion, native 1C/EDT, metadata/drafts/diff, live apply, macOS, model quality
or the complete Linux suite. The immutable existing accepted profiles and the
full final-release plan remain separate.
