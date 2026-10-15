# Rentgen Anatomy Explorer (review candidate)

The atlas visualizes a fixed accepted source snapshot, commit `6c8feb291dd251826eebb99e145f4a39f56cda47`, tree `7dcb248efdf33ca3ef93ce0f5d12b569ec02fe46`: 14 systems, 1,031 files, 5,465 declarations. No pending PR functionality is treated as accepted. No product code is executed by extraction or the viewer.

## Explore

Semantic 3D shapes organize real source systems into entry, context, analysis, changes and evidence lanes. Click a shape to inspect it, then Open to reveal its source-backed cutaway. A persistent named shell surrounds up to four clearly editorial directory/role compartments. Each exposes up to two exact-source representative files and an exact remainder count; a focused file/declaration stays in its containing compartment. The complete searchable source tree is never truncated. Role/directory facets, global search, pagination, exact source text, static dependency edges and bounded source routes are supported. The original assembly illustration, 2D graph and source browser remain accessible.

Drag to orbit, Shift-drag to pan, wheel/pinch to zoom. Arrow keys rotate and tilt; Enter opens; Escape goes up; H resets. Back/forward restores camera, route selection and per-system opening. The selected-system opening slider in the overview moves only that assembly; it is disabled for file/declaration scenes. The global slider applies to all groups and clears per-system overrides. Reset returns every assembly to its initial pose. The detail cover control synchronizes a real hinge, two compartment slides and a nested source focus. Closed/transitional interiors are not pointer/keyboard targets. Imports are opt-in and bounded to six immediate neighbors and twelve projected relations; direction/evidence stays available in the inspector. A persistent eight-route reading rail coordinates system, compartment, file/declaration and exact code, without autoplay. On mobile readable compartment tabs, source tree and a fixed selection card replace projected callouts.

Form and size are explanatory, not performance measurements. Detail colors indicate language; declaration/line counts are actual metadata. Python declarations use AST; other languages use lexical declaration locations, not full syntax/body parsing. Imports are not a call graph. The eight reading routes and thirteen architecture relations are clearly distinguished editorial interpretations, not runtime traces. No live telemetry or automatic product execution is present.

## Build from exact Git objects

Requirements: Node24, Python3.12, Git. From this directory:

```
python3 tools/extract_anatomy.py --repo ../.. --commit 6c8feb291dd251826eebb99e145f4a39f56cda47 --output .
python3 tools/verify_generated.py --output .
npm run build
```

See data/README.md for extraction/hash verification and the compact editorial seed. The extractor refuses a different tree. Generated datasets and viewer artifacts are deliberately excluded from source control.

`dist/index.html` is the hosted viewer. It fetches exact source text from same-origin `source-texts.json` on first inspection. `offline/Rentgen_Anatomy_Explorer.html` is the fully standalone variant. Source is escaped text; it is never executed. The original source payload and hash preserve exact bytes; CRLF/LF/CR line boundaries are normalized only for display. Build-time duration fields remain in geometry reports but are omitted from the distributable payload, so independent builds of the same source have stable hashes. The hosted CSP allows same-origin reads; offline permits no connections.

## Toolkit and checks

Anatomy is vendored under its MIT license, pinned to upstream commit `e6600ffc4e8e6620eeb45bf49bcdbd5e4b84163f`. See LOCAL-ANATOMY-PATCH.md for the preexisting exact-transform precision correction and the narrowly scoped conservative free-rotation pair coverage correction. Audit thresholds are unchanged.

Fresh full geometry qualification passed for both the 84-solid overview and the new 31-solid cutaway with four moving child groups under the current runtime, with zero failures in all sixteen categories. See [CUTAWAY-QUALIFICATION.md](CUTAWAY-QUALIFICATION.md) for exact import manifests, geometry-equivalence evidence and finite-sampling limits; `npm run qa:cutaway` reproduces the cutaway audit. Historical overview evidence, including its supplemental 252-pose depth check, remains documented in GEOMETRY-QUALIFICATION.md as provenance. The separate same-group and thin-overlap regression scripts reproduce the respective pre-fix failures and verify their corrections. `npm test` requires `npm install --ignore-scripts` and runs source-partition and DOM-only checks. It does not replace browser tests.

The separate `tests/anatomy-browser` suite performs real sandboxed Chromium interaction, mobile/desktop screenshots, exact-source verification and a HEAD/hash receipt. Its [workflow](../../.github/workflows/anatomy-browser-ci.yml) is read-only, uses no secrets, and does not deploy or release. Results and screenshots apply to the exact tested HEAD. The workflow filters atlas/test paths; unrelated changes or a merge to `main` do not constitute a fresh browser qualification. Each new atlas candidate requires its own successful run and screenshot review.

Current cutaway qualification, source partitions, exact import manifests and browser acceptance paths: [CUTAWAY-QUALIFICATION.md](CUTAWAY-QUALIFICATION.md). Browser qualification remains a separate exact-HEAD CI gate.
