# Experimental Linux supplement: candidate and acceptance

This independent packager does not change the four-file Windows Core contract.
It creates three supplement files in a new directory:

- `rentgen-core-VERSION-experimental-linux-x86_64.tar.gz`
- `experimental-linux-manifest.json`
- `experimental-linux-SHA256SUMS`

It never builds or executes a binary, installs a wheel, downloads inputs, creates
a tag or publishes. Python 3.11+ is required for the packager. Local staging must
be owned by the operator and protected from concurrent mutation. Input and output
paths must not traverse symlinks; files must be regular and have a single link.
Wheel/binary and archive limits are 64 MiB and 128 MiB respectively; unpacked tar
is limited to 128 MiB and 256 regular members. Source notices total at most 16 MiB.

## 1. Pin independently verified inputs

Verify the successful exact-source Windows and Linux CI run/artifact identities
and downloaded artifact digests before packaging. Extract the canonical wheel
from the accepted Windows kit without changing it. Select the exact Linux CI
binary, not a local rebuild. The packager checks both file hashes and lengths.
It records artifact IDs/digests as provenance, but does not query GitHub or prove
that a run was successful. That evidence must be reviewed independently.

Create an external `INPUTS.json` with exactly these fields (replace all placeholders):

```json
{
  "schema": 1,
  "version": "0.1.0.dev17",
  "rust_component_version": "0.1.0",
  "source_commit": "40_lowercase_hex_characters",
  "source_tree": "40_lowercase_hex_characters",
  "windows_kit": {
    "asset": "rentgen-core-0.1.0.dev17-windows-py311.zip",
    "sha256": "64_lowercase_hex_characters",
    "size_bytes": 1,
    "ci_run": 1,
    "artifact_id": 1,
    "artifact_sha256": "64_lowercase_hex_characters"
  },
  "wheel": {
    "asset": "rentgen_core-0.1.0.dev17-py3-none-any.whl",
    "sha256": "64_lowercase_hex_characters",
    "size_bytes": 1
  },
  "linux_ci": {
    "ci_run": 1,
    "artifact_id": 1,
    "artifact_sha256": "64_lowercase_hex_characters",
    "artifact_size_bytes": 1,
    "python": "3.12"
  },
  "binary": {
    "asset": "rentgen-input-core",
    "sha256": "64_lowercase_hex_characters",
    "size_bytes": 1
  }
}
```

`windows_kit.sha256` identifies the inner Windows delivery ZIP;
`windows_kit.artifact_sha256` identifies the downloaded GitHub artifact wrapper.
They are different objects. `linux_ci.artifact_sha256` also identifies the GitHub
artifact wrapper. `wheel.sha256` and `binary.sha256` identify the exact delivered
component bytes, independently of wrappers. Linux CI Python must be 3.11 or 3.12.

The source commit must be in checkout history and its tree and component versions
must match. MIT, Cargo.lock, protocol, dependency provenance and every Rust notice
are read from that commit's Git blobs, never from a modified working tree.
The wheel's package identity and binary's ELF64 x86_64 header are also checked.
These checks do not establish runtime compatibility; installed acceptance does.

## 2. Build and review a candidate

```sh
python scripts/release/prepare_experimental_linux.py build \
  --inputs INPUTS.json --wheel EXACT_WHEEL.whl --binary EXACT_LINUX_BINARY \
  --output NEW_CANDIDATE_DIRECTORY
```

Repeat into a second new directory and compare all three files byte-for-byte.
The tar uses sorted regular files, fixed timestamps/owners, no symlinks/hardlinks
or extension headers, 0755 for `bin/rentgen-input-core` and 0644 for all others.
Gzip filename/time are fixed. Determinism is checked in the same Python/zlib
packaging environment; cross-zlib compressed-byte reproducibility is not claimed.
Verification hash-checks the accepted compressed bytes and compares canonical
uncompressed tar bytes, without requiring the verifier's zlib to reproduce gzip.
The manifest binds source commit/tree, input hashes/provenance, platform limits,
archive hash/size and exact member names, hashes, sizes and decimal modes.

Build reports `candidate: true, accepted: false`. Review the candidate and its
provenance separately. Keep candidates outside the repository until reviewed.
The archive contains its own scoped `INSTALL.md` and `build-inputs.json`.

## 3. Commit reviewed records, verify and qualify delivered bytes

After review, commit the exact generated `experimental-linux-manifest.json` under
`releases/core/VERSION/`, alongside the accepted canonical Windows `manifest.json`.
The verifier and both records must be committed and unchanged. Acceptance checks
cross-reference Windows source/version/kit/wheel/run identity; they reject new or
missing output files, altered metadata, unbounded/special/duplicate/unsafe tar
members and noncanonical payloads, including hidden or trailing archive data.
Original license/provenance bytes must still match the source commit.

```sh
python scripts/release/prepare_experimental_linux.py verify \
  --version 0.1.0.dev17 --output NEW_CANDIDATE_DIRECTORY \
  --extract NEW_EXTRACTED_DIRECTORY
python scripts/verification/verify_portable_delivery.py \
  --wheel NEW_EXTRACTED_DIRECTORY/rentgen_core-0.1.0.dev17-py3-none-any.whl \
  --binary NEW_EXTRACTED_DIRECTORY/bin/rentgen-input-core \
  --expected-version 0.1.0.dev17 --output NEW_INSTALLED_SMOKE_DIRECTORY
```

Extraction is optional, uses a fresh directory and only writes files after full
validation. It returns the extracted wheel and binary paths for the existing
fresh-installed smoke. Run that smoke on the claimed Linux/Python environment;
retain and review its `acceptance.json` with release evidence. A hash verification
result alone does not claim the installed smoke passed. If acceptance fails,
do not publish; revise/replace the candidate and its reviewed record explicitly.

Scope is experimental GNU/Linux x86_64 with glibc >= 2.34, `libgcc_s.so.1`, Linux
>= 5.9, memfd seals and `/proc/self/fd`. Full Linux is not green: 90 known failures
and 2 errors remain. This supplement does not qualify native 1C, Editor, Observer,
live apply, macOS, model quality, acceleration or full product readiness. It is
not an offline MCP-dependency kit. Any publication is a separate authorized step.

## Focused tests

```sh
python -m pytest -q tests/unit/test_experimental_linux_release.py tests/unit/test_core_release.py
```

Fixtures use synthetic wheel/binary inputs and do not substitute for actual
installed CLI acceptance. Neither packager nor tests change runtime, wheel,
sdist or VSIX inputs.
