# Reproducible pinned source atlas

The accepted source pin is `6c8feb291dd251826eebb99e145f4a39f56cda47`, exact Git tree `7dcb248efdf33ca3ef93ce0f5d12b569ec02fe46`, in `DmitrL-dev/1cai-public`.

## Build and verify

Use Python 3.12, its standard library, and Git. The supplied Git repository must already contain the exact commit and blobs (CI can use its normal checkout with `fetch-depth: 0`). No package installation is needed for extraction.

```sh
python3 tools/extract_anatomy.py --repo /path/to/product-repository \
  --commit 6c8feb291dd251826eebb99e145f4a39f56cda47 --output .
python3 tools/verify_generated.py --output .
node build.mjs
```

The source repository may be the same repository containing this UI builder. `--output` can name a separate build directory. Output files are `architecture.json`, `source-texts.json`, `inventory.json`, `coverage.json`, `sections.json`, `validation.json`, and `artifact-manifest.json`. They are generated build inputs and should not be committed. Only this compact seed, manifest and owned extraction scripts are required.

`editorial-seed.json` is approximately 378KB: source-path classification, 217 editorial node deltas, system descriptions, reviewed routes, boundary explanations, historical status evidence and exact source references. It does not contain complete source files. `source-manifest.json` binds this seed to the reviewed commit/tree and deterministic generated artifact hashes.

The extractor rejects any other commit/tree. Updating the source pin requires reviewing affected annotations and refreshing the seed and manifest. Timestamps use the pinned commit time. No workspace-specific paths, prior scratch files, credentials or network setup are embedded.

## Source and interaction contract

Stable IDs are `file:<path>` and `symbol:<path>:<qualified Python name>`. Other supported declarations use `symbol:<path>:<name>@<line>`, so those IDs are line-addressed. `parentId` represents system/file/symbol hierarchy; physical folders are in `directories[]`, with each file's `directoryId` kept separately.

Text nodes expose 1-based inclusive `line`/`endLine`. Python spans come from AST parsing. Non-Python lexical declarations expose only their declaration line, not a complete function body. Three PNG nodes have `sourceTextAvailable=false`, no fabricated line spans, and ordinary blob refs.

`source-texts.json` has `{meta, files: {path: {text, lineCount, sha256, blobSha, encoding}}}`. Display source with escaped text, never HTML interpretation or script execution; render a bounded window around the selected node. Full text remains available for navigation beyond the displayed window.

Import edges have `evidenceKind=static_import` and `sourceSyntax`; these are file-level dependencies, not runtime calls. Thirteen cross-system architecture edges have `evidenceKind=inferred_architecture`. `flows[]` and `semanticRoutes[]` are aliases for the same eight editorial routes; do not count them twice. Three native component routes are in `nativeDetails.flows`. All semantic routes are marked inferred and `isExecutionTrace=false`.

PR91/92 are excluded pending features. Historical PR87 CI records and PR84 candidate evidence do not claim a current test run. Source acceptance does not imply a release or that the experimental Rust kernel is product-integrated.

## Fresh verification after workspace reset

The original published source ZIP was restored from Library. Its architecture supplied the recovered editorial baseline. The unpersisted extraction code and compact seed were lost and have been recreated, rather than represented as byte-restored files. Source objects were independently fetched from GitHub and the accepted pin/tree was checked anew.

Every generated file is byte-checked against its Git blob SHA-1 and has a SHA-256. Fresh validation confirms 1,031 tracked files, 6,496 unique nodes, 5,465 declarations, 1,334 resolved import dependencies, 15,443 valid source-bearing objects, no dangling hierarchy/edge/route IDs, and zero Python parse errors. Source text covers 1,028 UTF-8 files; three PNGs are excluded. Two post-reset runs in separate output directories produced byte-identical six-artifact manifests. Prior pre-reset hash proofs are not reused.

The recreated extractor normalizes legacy duplicate navigation tags. Its JSON metadata and validation explicitly record recovery provenance; byte identity with the lost pre-reset outputs is not claimed. Semantic annotations and IDs remain compatible with the original atlas.

## Static-only limits

The extractor reads Git objects and a Git archive directly in memory. Unsafe paths, symlinks, submodules and special entries are rejected. It never imports or executes project code, setup scripts, tests, plugins, binaries or build tools. Only the owned `extract_index` module is imported.

Coverage means complete tracked-file indexing. It is not comprehensive semantic review, full non-Python AST coverage, exhaustive dependency resolution, callgraph precision, runtime evidence or test coverage. Dynamic imports, computed receivers and unresolved calls are not exhaustively represented. Source and derived text are data only.
