# Rentgen Anatomy Explorer (review candidate)

The atlas visualizes accepted source commit `6c8feb291dd251826eebb99e145f4a39f56cda47`, tree `7dcb248efdf33ca3ef93ce0f5d12b569ec02fe46`: 14 systems, 1,031 files, 5,465 declarations. No pending PR functionality is treated as accepted. No product code is executed by extraction or the viewer.

## Explore

Semantic 3D shapes organize real source systems into entry, context, analysis, changes and evidence lanes. Click a shape to inspect it, then Open to see actual files and declarations. Role/directory facets, global search, pagination, exact source text, static dependency edges and bounded source routes are supported. The original assembly illustration, 2D graph and source browser remain accessible.

Drag to orbit, Shift-drag to pan, wheel/pinch to zoom. Arrow keys rotate and tilt; Enter opens; Escape goes up; H resets. Back/forward restores camera and route selection. On mobile a readable fixed selection card and object list replace tiny projected labels.

Form and size are explanatory, not performance measurements. Detail colors indicate language; declaration/line counts are actual metadata. Python declarations use AST; other languages use lexical declaration locations, not full syntax/body parsing. Imports are not a call graph. The eight reading routes and thirteen architecture relations are clearly distinguished editorial interpretations, not runtime traces. No live telemetry or automatic product execution is present.

## Build from exact Git objects

Requirements: Node24, Python3.12, Git. From this directory:

```
python3 tools/extract_anatomy.py --repo ../.. --commit 6c8feb291dd251826eebb99e145f4a39f56cda47 --output .
python3 tools/verify_generated.py --output .
npm run build
```

See data/README.md for extraction/hash verification and the compact editorial seed. The extractor refuses a different tree. Generated datasets and viewer artifacts are deliberately excluded from source control.

`dist/index.html` is the hosted viewer. It fetches exact source text from same-origin `source-texts.json` on first inspection. `offline/Rentgen_Anatomy_Explorer.html` is the fully standalone variant. Source is escaped text; it is never executed. The hosted CSP allows same-origin reads; offline permits no connections.

## Toolkit and checks

Anatomy is vendored under its MIT license, pinned to upstream commit `e6600ffc4e8e6620eeb45bf49bcdbd5e4b84163f`. See LOCAL-ANATOMY-PATCH.md for the preexisting exact-transform precision correction and the narrowly scoped conservative free-rotation pair coverage correction. Audit thresholds are unchanged.

Build and focused regression/quick geometry checks passed in the recovered worktree. The full geometry process was interrupted at depth oracle and is not claimed as passed. `node qa/explorer-free-pair-regression.mjs` reproduces the upstream defect and checks the correction. `npm test` requires `npm install --ignore-scripts` and runs DOM-only checks. It does not replace browser tests.

The separate `tests/anatomy-browser` suite performs real sandboxed Chromium interaction, mobile/desktop screenshots, exact-source verification and a HEAD/hash receipt. Its workflow is read-only, uses no secrets, and does not deploy or release. Browser qualification is pending until that exact candidate completes CI and screenshots are reviewed.
