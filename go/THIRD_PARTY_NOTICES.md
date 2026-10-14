# Go 1.25.5 notices for experimental Linux images

Rentgen's own source remains under the repository-root MIT [LICENSE](../LICENSE).
The `bsl-source-facts` executable also incorporates the Go runtime and standard
library. Their license is not replaced by Rentgen's MIT license.

The `go.mod` file declares Go 1.25.5 and no third-party module requirements.
[licenses/go1.25.5](licenses/go1.25.5/) preserves the exact official distribution's
BSD-style `LICENSE`, additional IP grant `PATENTS`, and `VERSION`. These notices
must accompany the experimental Go executable together with Rentgen's license.

The small `source-notices` bundle additionally preserves complete comment-only
notice excerpts from the amd64 runtime's Inferno-derived `memmove` (Lucent and
Vita Nuova), Sun's 1993 and 2004 math notices, and the Cephes/Stephen L. Moshier
math notice. Original text, comment markers, line endings and attributions are
unchanged. No implementation source is copied into these excerpts. Retaining a
notice does not claim that every function from its source file is linked.

[PROVENANCE.json](licenses/go1.25.5/PROVENANCE.json) records the official Linux
amd64 archive URL, SHA-256 and size, full source-file hashes, inclusive excerpt
lines and copied-byte hashes/sizes. Each original was compared with its exact
member in the verified Go 1.25.5 archive. [SHA256SUMS](licenses/go1.25.5/SHA256SUMS)
covers the copied files and provenance record; verify it from that directory.
CI also compares those source files and excerpts against its actual Go 1.25.5
installation before qualification.

This is a bounded source-notice inventory for this experimental image. It is not
an exhaustive transitive linker attribution audit or legal clearance. Go's tools,
optional standard-library integrations and unrelated vendored tools are not
redistributed here. The bundle contains no third-party module source cache.
The Rust crates retain their existing, separate dependency and standard-library
notice bundles unchanged.
