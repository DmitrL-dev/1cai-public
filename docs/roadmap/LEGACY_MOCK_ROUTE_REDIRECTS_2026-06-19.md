# Legacy Mock Route Redirects - 2026-06-19

## Why

The main buyer sidebar no longer exposed old generic pages, but direct URLs such as `/wiki`, `/bpmn` and `/marketplace`
still rendered mock/sample content. That creates a "monster product" smell: one stray bookmark can make the buyer think
the product contains unfinished generic modules.

## Implemented

- `/wiki` now redirects to `/evidence-bundle`.
- `/bpmn` now redirects to `/architecture`.
- `/marketplace` now redirects to `/value-packs`.
- The route files remain present, so old links do not 404, but they lead to real 1C Rentgen product surfaces.

## Buyer Impact

Old or manually-entered URLs no longer show sample marketplace/wiki/BPMN screens.
The buyer stays inside the evidence, architecture and value-pack story instead of seeing unrelated mock UI.

## Verification

- `npm.cmd run build`
