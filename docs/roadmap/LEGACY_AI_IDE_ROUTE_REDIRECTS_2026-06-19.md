# Legacy AI / IDE Route Redirects - 2026-06-19

## Why

The main navigation already pushes buyers into Launch Room, Killer Demo, Evidence Bundle, Safe Autopilot and the engineering/trust workbenches.
But hidden direct URLs still exposed old generic screens:

- `/copilot` with "AI Copilot" positioning;
- `/code-review` with "AI-powered analysis";
- `/rentgen` with a legacy call graph UI and mojibake labels;
- `/ide` with a partial IDE surface.

Those screens contradicted the current product story: 1C Rentgen is a local evidence/control plane, not another generic AI chat or half-built IDE.

## Implemented

- `/copilot` redirects to `/safe-autopilot`.
- `/code-review` redirects to `/quality`.
- `/rentgen` redirects to `/`.
- `/ide` redirects to `/workbench`.
- Old heavy route content is no longer bundled by the portal build.

## Buyer Impact

Old bookmarks no longer expose generic AI/IDE pages.
They land in the current product path: safe planning, quality evidence, first-screen buyer path or delivery workbench.

## Verification

- `npm.cmd run build`
- Search confirms old route copy such as `AI Copilot`, `AI-powered analysis`, `1C:IDE` and `Call Graph Analysis` is gone from authenticated route sources.
