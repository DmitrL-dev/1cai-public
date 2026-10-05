# Third-party license and notice inventory

This bundle accompanies the Rentgen Rust input-core deliverable. It inventories every one of the **42 registry packages in Cargo.lock**, including optional and target-specific packages. Inclusion does not assert that a package is linked into a particular binary or select among alternative licenses. The Rentgen project's own license is in the repository-root [LICENSE](../../LICENSE) and should accompany distribution separately.

## Provenance and verification

- Inventory date: 2026-10-05.
- Cargo.lock SHA-256: `efd4f39a444413df5091a0409831e5e63f3ce0b618e4865faf84adf80a1e549c`.
- Package metadata comes from each locked version's vendored Cargo.toml `[package]` section; license expressions are reproduced verbatim, including `version_check`'s historical `MIT/Apache-2.0` spelling.
- [packages.tsv](licenses/packages.tsv) records package/version, declared license and license-file fields, repository and registry links, locked registry archive checksum, and Cargo.toml SHA-256. None of these 42 package manifests declares a `license-file` field.
- **92 complete standalone license/copyright/notice files** are copied byte-for-byte from those packages. Each copied file and each package manifest was checked against the package's `.cargo-checksum.json`; the manifest's registry package checksum was checked against Cargo.lock.
- **35 additional comment-only excerpts** preserve embedded copyright, licensing, and provenance notices. Their original bytes, comment markers, and line endings are preserved. Source paths, exact inclusive line ranges, full source-file hashes, excerpt hashes, and sizes are in [files.tsv](licenses/files.tsv). Source files were also checked against vendor checksums. No implementation code is included in these excerpts.
- A separate **Rust standard-library notice file** is preserved from the installed Rust 1.92.0 toolchain: [COPYRIGHT-library.html](licenses/rust-standard-library-1.92.0/COPYRIGHT-library.html). Its original toolchain-relative path is `share/doc/rust/COPYRIGHT-library.html`; its source and copied bytes were compared. It covers the standard library's own source and dependency notices, and is outside the 42-package Cargo inventory. The HTML notice is retained as supplied, not executed.
- [SHA256SUMS](licenses/SHA256SUMS) covers this notice, every copied notice, both inventories, and the complete added-file list. Run `sha256sum -c licenses/SHA256SUMS` from `rust/input-core` to verify. The checksum manifest excludes itself.

## Observed gaps and boundaries

No standalone text is missing for a license alternative explicitly declared in these 42 Cargo.toml package license fields. This is an inventory result, not legal clearance or an exhaustive attribution audit.

1. **caseless 0.2.2:** Cargo.toml declares MIT and the package includes its MIT LICENSE. Bundled `CaseFolding.txt` identifies Unicode Character Database 16.0.0, carries a 2024 Unicode, Inc. copyright/trademark notice, and links to [Unicode terms of use](https://www.unicode.org/terms_of_use.html). The exact first eight lines are [preserved here](licenses/caseless-0.2.2/source-notices/CaseFolding.txt.lines-1-8.txt). This package does **not** bundle the complete Unicode license text. No alternative or later license text has been substituted.
2. **unicode-normalization 0.1.25:** The package includes its declared MIT and Apache texts and COPYRIGHT. Its generator identifies Unicode data tables, and the generated table identifies Unicode 17.0.0; the package does not include a separate Unicode data license text. The generator's existing attribution and table-provenance comments are [preserved here](licenses/unicode-normalization-0.1.25/source-notices/scripts/unicode.py.lines-3-20.txt). This observation does not decide what additional obligations apply.
3. **Other embedded provenance references:** Preserved excerpts include Rust standard-library derivations, serde_json's Alexander Huszagh attribution, sha2's mbedtls adaptation notes, simd-adler32's Chromium zlib reference, and libc/hashbrown source-origin references. These references are retained as supplied; external origins and any additional obligations have not been independently resolved. Package-level license texts have not been relabeled on the strength of a source comment.
4. Some source notices reference a Rust COPYRIGHT file that the individual crate does not supply. Those references remain unchanged in the preserved excerpts. The separate installed standard-library notice is included as an additional original artifact, without claiming it replaces every historical reference.
5. `unicode-ident` declares `(MIT OR Apache-2.0) AND Unicode-3.0`; its full LICENSE-UNICODE is included alongside its Apache and MIT texts. The `AND` relationship is preserved in the inventory.

## Package index

For every row, `license-file` is **not declared**. Registry URLs identify the exact locked versions; repository URLs are copied from each package manifest. The linked directory retains the original standalone notice filenames and any separately identified source-notice excerpts.

| Package | Version | Declared license expression | Source repository | Exact registry version | Notices |
|---|---|---|---|---|---|
| adler2 | 2.0.1 | `0BSD OR MIT OR Apache-2.0` | [Repository](https://github.com/oyvindln/adler2) | [crates.io](https://crates.io/crates/adler2/2.0.1) | [Files](licenses/adler2-2.0.1/) |
| base64 | 0.22.1 | `MIT OR Apache-2.0` | [Repository](https://github.com/marshallpierce/rust-base64) | [crates.io](https://crates.io/crates/base64/0.22.1) | [Files](licenses/base64-0.22.1/) |
| bitflags | 2.11.1 | `MIT OR Apache-2.0` | [Repository](https://github.com/bitflags/bitflags) | [crates.io](https://crates.io/crates/bitflags/2.11.1) | [Files](licenses/bitflags-2.11.1/) |
| block-buffer | 0.10.4 | `MIT OR Apache-2.0` | [Repository](https://github.com/RustCrypto/utils) | [crates.io](https://crates.io/crates/block-buffer/0.10.4) | [Files](licenses/block-buffer-0.10.4/) |
| caseless | 0.2.2 | `MIT` | [Repository](https://github.com/unicode-rs/rust-caseless) | [crates.io](https://crates.io/crates/caseless/0.2.2) | [Files](licenses/caseless-0.2.2/) |
| cfg-if | 1.0.4 | `MIT OR Apache-2.0` | [Repository](https://github.com/rust-lang/cfg-if) | [crates.io](https://crates.io/crates/cfg-if/1.0.4) | [Files](licenses/cfg-if-1.0.4/) |
| cpufeatures | 0.2.17 | `MIT OR Apache-2.0` | [Repository](https://github.com/RustCrypto/utils) | [crates.io](https://crates.io/crates/cpufeatures/0.2.17) | [Files](licenses/cpufeatures-0.2.17/) |
| crc32fast | 1.5.0 | `MIT OR Apache-2.0` | [Repository](https://github.com/srijs/rust-crc32fast) | [crates.io](https://crates.io/crates/crc32fast/1.5.0) | [Files](licenses/crc32fast-1.5.0/) |
| crypto-common | 0.1.7 | `MIT OR Apache-2.0` | [Repository](https://github.com/RustCrypto/traits) | [crates.io](https://crates.io/crates/crypto-common/0.1.7) | [Files](licenses/crypto-common-0.1.7/) |
| digest | 0.10.7 | `MIT OR Apache-2.0` | [Repository](https://github.com/RustCrypto/traits) | [crates.io](https://crates.io/crates/digest/0.10.7) | [Files](licenses/digest-0.10.7/) |
| equivalent | 1.0.2 | `Apache-2.0 OR MIT` | [Repository](https://github.com/indexmap-rs/equivalent) | [crates.io](https://crates.io/crates/equivalent/1.0.2) | [Files](licenses/equivalent-1.0.2/) |
| errno | 0.3.14 | `MIT OR Apache-2.0` | [Repository](https://github.com/lambda-fairy/rust-errno) | [crates.io](https://crates.io/crates/errno/0.3.14) | [Files](licenses/errno-0.3.14/) |
| flate2 | 1.1.9 | `MIT OR Apache-2.0` | [Repository](https://github.com/rust-lang/flate2-rs) | [crates.io](https://crates.io/crates/flate2/1.1.9) | [Files](licenses/flate2-1.1.9/) |
| generic-array | 0.14.7 | `MIT` | [Repository](https://github.com/fizyk20/generic-array.git) | [crates.io](https://crates.io/crates/generic-array/0.14.7) | [Files](licenses/generic-array-0.14.7/) |
| hashbrown | 0.17.1 | `MIT OR Apache-2.0` | [Repository](https://github.com/rust-lang/hashbrown) | [crates.io](https://crates.io/crates/hashbrown/0.17.1) | [Files](licenses/hashbrown-0.17.1/) |
| indexmap | 2.14.0 | `Apache-2.0 OR MIT` | [Repository](https://github.com/indexmap-rs/indexmap) | [crates.io](https://crates.io/crates/indexmap/2.14.0) | [Files](licenses/indexmap-2.14.0/) |
| itoa | 1.0.18 | `MIT OR Apache-2.0` | [Repository](https://github.com/dtolnay/itoa) | [crates.io](https://crates.io/crates/itoa/1.0.18) | [Files](licenses/itoa-1.0.18/) |
| libc | 0.2.186 | `MIT OR Apache-2.0` | [Repository](https://github.com/rust-lang/libc) | [crates.io](https://crates.io/crates/libc/0.2.186) | [Files](licenses/libc-0.2.186/) |
| linux-raw-sys | 0.12.1 | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | [Repository](https://github.com/sunfishcode/linux-raw-sys) | [crates.io](https://crates.io/crates/linux-raw-sys/0.12.1) | [Files](licenses/linux-raw-sys-0.12.1/) |
| memchr | 2.8.0 | `Unlicense OR MIT` | [Repository](https://github.com/BurntSushi/memchr) | [crates.io](https://crates.io/crates/memchr/2.8.0) | [Files](licenses/memchr-2.8.0/) |
| miniz_oxide | 0.8.9 | `MIT OR Zlib OR Apache-2.0` | [Repository](https://github.com/Frommi/miniz_oxide/tree/master/miniz_oxide) | [crates.io](https://crates.io/crates/miniz_oxide/0.8.9) | [Files](licenses/miniz_oxide-0.8.9/) |
| proc-macro2 | 1.0.106 | `MIT OR Apache-2.0` | [Repository](https://github.com/dtolnay/proc-macro2) | [crates.io](https://crates.io/crates/proc-macro2/1.0.106) | [Files](licenses/proc-macro2-1.0.106/) |
| quote | 1.0.45 | `MIT OR Apache-2.0` | [Repository](https://github.com/dtolnay/quote) | [crates.io](https://crates.io/crates/quote/1.0.45) | [Files](licenses/quote-1.0.45/) |
| rustix | 1.1.4 | `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | [Repository](https://github.com/bytecodealliance/rustix) | [crates.io](https://crates.io/crates/rustix/1.1.4) | [Files](licenses/rustix-1.1.4/) |
| serde | 1.0.228 | `MIT OR Apache-2.0` | [Repository](https://github.com/serde-rs/serde) | [crates.io](https://crates.io/crates/serde/1.0.228) | [Files](licenses/serde-1.0.228/) |
| serde_core | 1.0.228 | `MIT OR Apache-2.0` | [Repository](https://github.com/serde-rs/serde) | [crates.io](https://crates.io/crates/serde_core/1.0.228) | [Files](licenses/serde_core-1.0.228/) |
| serde_derive | 1.0.228 | `MIT OR Apache-2.0` | [Repository](https://github.com/serde-rs/serde) | [crates.io](https://crates.io/crates/serde_derive/1.0.228) | [Files](licenses/serde_derive-1.0.228/) |
| serde_json | 1.0.149 | `MIT OR Apache-2.0` | [Repository](https://github.com/serde-rs/json) | [crates.io](https://crates.io/crates/serde_json/1.0.149) | [Files](licenses/serde_json-1.0.149/) |
| sha2 | 0.10.9 | `MIT OR Apache-2.0` | [Repository](https://github.com/RustCrypto/hashes) | [crates.io](https://crates.io/crates/sha2/0.10.9) | [Files](licenses/sha2-0.10.9/) |
| simd-adler32 | 0.3.9 | `MIT` | [Repository](https://github.com/mcountryman/simd-adler32) | [crates.io](https://crates.io/crates/simd-adler32/0.3.9) | [Files](licenses/simd-adler32-0.3.9/) |
| syn | 2.0.117 | `MIT OR Apache-2.0` | [Repository](https://github.com/dtolnay/syn) | [crates.io](https://crates.io/crates/syn/2.0.117) | [Files](licenses/syn-2.0.117/) |
| tinyvec | 1.11.0 | `Zlib OR Apache-2.0 OR MIT` | [Repository](https://github.com/Lokathor/tinyvec) | [crates.io](https://crates.io/crates/tinyvec/1.11.0) | [Files](licenses/tinyvec-1.11.0/) |
| tinyvec_macros | 0.1.1 | `MIT OR Apache-2.0 OR Zlib` | [Repository](https://github.com/Soveu/tinyvec_macros) | [crates.io](https://crates.io/crates/tinyvec_macros/0.1.1) | [Files](licenses/tinyvec_macros-0.1.1/) |
| typed-path | 0.12.3 | `MIT OR Apache-2.0` | [Repository](https://github.com/chipsenkbeil/typed-path) | [crates.io](https://crates.io/crates/typed-path/0.12.3) | [Files](licenses/typed-path-0.12.3/) |
| typenum | 1.20.0 | `MIT OR Apache-2.0` | [Repository](https://github.com/paholg/typenum) | [crates.io](https://crates.io/crates/typenum/1.20.0) | [Files](licenses/typenum-1.20.0/) |
| unicode-ident | 1.0.24 | `(MIT OR Apache-2.0) AND Unicode-3.0` | [Repository](https://github.com/dtolnay/unicode-ident) | [crates.io](https://crates.io/crates/unicode-ident/1.0.24) | [Files](licenses/unicode-ident-1.0.24/) |
| unicode-normalization | 0.1.25 | `MIT OR Apache-2.0` | [Repository](https://github.com/unicode-rs/unicode-normalization) | [crates.io](https://crates.io/crates/unicode-normalization/0.1.25) | [Files](licenses/unicode-normalization-0.1.25/) |
| version_check | 0.9.5 | `MIT/Apache-2.0` | [Repository](https://github.com/SergioBenitez/version_check) | [crates.io](https://crates.io/crates/version_check/0.9.5) | [Files](licenses/version_check-0.9.5/) |
| windows-link | 0.2.1 | `MIT OR Apache-2.0` | [Repository](https://github.com/microsoft/windows-rs) | [crates.io](https://crates.io/crates/windows-link/0.2.1) | [Files](licenses/windows-link-0.2.1/) |
| windows-sys | 0.61.2 | `MIT OR Apache-2.0` | [Repository](https://github.com/microsoft/windows-rs) | [crates.io](https://crates.io/crates/windows-sys/0.61.2) | [Files](licenses/windows-sys-0.61.2/) |
| zip | 7.2.0 | `MIT` | [Repository](https://github.com/zip-rs/zip2.git) | [crates.io](https://crates.io/crates/zip/7.2.0) | [Files](licenses/zip-7.2.0/) |
| zmij | 1.0.21 | `MIT` | [Repository](https://github.com/dtolnay/zmij) | [crates.io](https://crates.io/crates/zmij/1.0.21) | [Files](licenses/zmij-1.0.21/) |
