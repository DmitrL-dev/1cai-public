# Local Anatomy builder correction

Upstream: wheresryan22/anatomy, commit `e6600ffc4e8e6620eeb45bf49bcdbd5e4b84163f`.
Original `kit/turn-build.mjs` Git blob: `3bfe31b9bb87c7d0b7b75f62054149bfa583fb1a`.

## Change

In the same-group pair loop, when a group has a free ancestor (`group.loose`), replace the world-space bounding-sphere proximity test with unconditional pair inclusion (`near = true`). This creates a separating plane for every rigid same-group convex pair. Other pair logic, runtime, geometry, source data, audit thresholds and camera ranges are unchanged.

## Why

Distant objects can overlap in projection after free rotation. World proximity is not a conservative bound for screen visibility. Upstream omitted a pair of graph-node solids; at the actual UI pose `Rx(-85°) * Rz(30°)`, the official depth oracle found one visible node drawn behind another. Adding pose samples cannot fix the upstream branch because it does not consult those samples.

The exact upstream source can be reconstructed by reversing this single branch/comment change; the regression verifies its Git blob hash before comparing it.

## Rejected approach

Putting every solid in a separate identity frame removed the missing-pair issue but introduced 22 contact-swap failures near edge-on flush contacts. That workaround was reverted. The final semantic scene retains 15 groups: one free world and 14 system slide groups. The corrected builder adds only 27 planes for this scene: 214 instead of 187.

## Checks

- `node qa/explorer-free-pair-regression.mjs`: exact upstream has six depth failures on the repeated failing pose; patched builder has zero. The 50°–65° flush-contact sweep passes both versions with zero swaps. This runs official order/depth checks, not a full audit.
- `node build-explorer-scene.mjs --audit --quick`: all categories have zero problems for the actual `Rx(pitch) * Rz(yaw)` composition, yaw sweep, pitch ±85°, and explosion. Quick sampling is explicitly not a full proof.
- `node build-explorer-scene.mjs --audit`: verified full PASS, exit 0, 360.47 s; every category has zero failures. The isolated qualification record is `qa/explorer-full-qualified-20261013.log`, with exact source hashes in `qa/explorer-full-qualified-execution-inputs.sha256`. The older reused log is not the qualification record.
- `node qa/explorer-mixed-depth.mjs`: supplemental unchanged full-resolution depth oracle PASS, exit 0; 252 mixed yaw/pitch/slide poses and 43,754 overlapping pairs, zero failures. This is depth-only coverage, not another full audit. See `GEOMETRY-QUALIFICATION.md` for the precise sampling contract and remaining limits.
- `node qa/explorer-scene-performance.mjs`: bounded original/patched comparison over mixed actual-UI poses and independent slides. Its JSON records costs. Node geometry timing is not browser frame rate.

The stock benchmark expects a turn root and does not support this free-root scene; the standard fidelity identity helper also targets turn roots. Their absence is not replaced by a misleading success claim. Real-browser order, interaction, clipping, label placement, accessibility and performance checks remain independent requirements.

The prior atlas already contained a separate exact-transform precision fix in `turn.mjs`. This new correction changes only `turn-build.mjs` and does not relax that earlier fidelity threshold.
