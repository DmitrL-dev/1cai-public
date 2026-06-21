# Portal Code Splitting

Date: 2026-06-19.

## Purpose

The portal build no longer ships one oversized application chunk. This keeps the first product impression faster
and removes the repeated Vite warning about chunks larger than 500 KB.

## Implemented

- Enabled TanStack Router `autoCodeSplitting` in `portal/vite.config.ts`.
- Added Rollup `manualChunks`:
  - `vendor`
  - `tanstack`
  - `icons`
  - `routes-deal`
  - `routes-trust`
  - `routes-engineering`
  - `routes-other`
- Kept chunk warning limits unchanged instead of hiding the warning.

## Verification

- `npm run build` in `portal/` passed without the previous 500 KB Vite chunk warning.
- Largest emitted JS chunk after the change: `vendor` at 465.51 KB.
- Live route smoke returned 200 for `/`, `/launch-room`, `/approvals` and `/audit`.

## Caveat

TanStack Router still emits a synchronous `routeTree.gen.ts` in this workspace, so route components are grouped by
Rollup chunking rather than fully lazy-loaded per route. A later pass can move individual heavy surfaces to explicit
lazy route files if first-load tracing shows a need.
