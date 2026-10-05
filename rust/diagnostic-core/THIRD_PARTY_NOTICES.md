# Third-party notices for the experimental diagnostic kernel

The crate is publish=false and uses the exact pinned serde 1.0.228 and serde_json
1.0.149 versions from the existing Rust input-core. This bundle preserves the
complete package-level notices and source-notice excerpts for all 11 registry
packages in the inherited lock subset, including proc-macro dependencies.

The repository-root [LICENSE](../../LICENSE) covers Rentgen code. The per-package
license expressions, repository links and locked checksums remain in
[packages.tsv](licenses/packages.tsv); copied original paths and source excerpts
remain in [files.tsv](licenses/files.tsv). The Rust 1.92.0 standard-library notice
is copied unchanged and lies outside the registry package count.

No license expressions have been simplified: unicode-ident retains
(MIT OR Apache-2.0) AND Unicode-3.0. Complete originals, including its Unicode
license, are copied rather than replaced by this summary. Embedded notices in
serde_json retain their original attribution and references. The source bundle's
provenance limitations still apply; this is not new legal or dependency clearance.

See [DEPENDENCY_PROVENANCE.json](DEPENDENCY_PROVENANCE.json) for inherited source
checksums and limits. No new registry packages, services, models or native probes
are introduced. The later offline Cargo --locked build and synthetic tests passed; see the
[qualification record](../../docs/product/DIAGNOSTIC-KERNEL-QUALIFICATION.json).
The inherited provenance record preserves its pre-build snapshot limits. The complete copied-file manifest is [SHA256SUMS](licenses/SHA256SUMS).
