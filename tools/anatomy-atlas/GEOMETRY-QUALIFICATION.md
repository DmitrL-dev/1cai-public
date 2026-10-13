# Explorer geometry qualification

This report applies to the 84-solid, 14-system semantic explorer, not the older 122-solid physical-atlas scene. Geometry explains source responsibilities; it is not physical hardware or runtime telemetry.

## Contract

- One free world group and 14 independently movable system groups, 84 convex solids.
- World rotation is `Rx(pitch) * Rz(yaw)`. Yaw is unrestricted modulo a full turn; pitch is bounded to −85° through +85°.
- Each system supports an independent radial slide of 0–22 scene units. This is the qualified geometry contract; UI control exposure and interaction behavior are covered separately by UI verification.
- All 214 rigid same-system convex pairs have separating planes. This is exactly the sum of `n * (n - 1) / 2` across the 14 systems. The upstream builder generated 187 planes.
- Neither the camera range nor official audit thresholds were reduced to obtain these results.

## Verified full audit

PASS: `node build-explorer-scene.mjs --audit`, exit 0, 360.47 seconds.

Evidence: `qa/explorer-full-qualified-20261013.log` and `qa/explorer-full-qualified-execution-inputs.sha256`.

The qualifying run used a fresh isolated output directory and copies of the frozen inputs. After completion, all recorded source hashes were checked against the working inputs. Its generated `turn`, `parts` and `objects` data exactly matched the working scene. The execution-input manifest contains exactly eight tracked source files: the builder and seven kit modules in its transitive import closure. Their hashes match the exact committed PR blobs recorded in `qa/explorer-audit-input-closure.json`. The required generated data input, architecture.json, is not tracked: its audited hash is preserved separately in `qa/explorer-full-qualified-generated-inputs.sha256` and matches the current generated PR data. The earlier 13-file working-directory comparison included four untracked incidental modules and was not proof of the committed package. Those modules are excluded from the corrected import manifest because none is imported, not because of a hash mismatch. The separate 17-file `qa/explorer-full-qualified-inputs.sha256` is archival snapshot inventory, not an execution-dependency claim. The historical `qa/explorer-scene-conservative-full.log` is not the qualification record because its filename was reused during recovery.

All 16 reported orbit categories contain zero failures: separation, unseparated, cycles, forced, swaps, layers, rigid, swept, posed, folds, self, crowding, endon, coverage, depth and continuity. The standard static geometry audit also passed.

- 2,835 order states and 946 posed states
- 214 separating planes; minimum margin 0, including intended flush contacts
- Full-resolution depth oracle: 72 states and 10,790 overlapping pairs
- 400 raster-halving cases; zero failures
- The 124 reported states with order changes are ordinary changes in draw order as objects move; the separate unexpected-swap failure count is zero

The full run uses the original complete audit categories and resolution. Its motion families cover 360° yaw, a −85°…+85° pitch sweep at yaw 30°, and assembly explosion; 104 additional authored poses cover mixed yaw/pitch extrema and individual system slides. These are finite sampled checks, not a mathematical proof of every point in the continuous pose space.

## Upstream regression

`node qa/explorer-free-pair-regression.mjs` passed again during qualification. The script reconstructs the exact upstream builder and checks its Git blob identity before comparing behavior.

- Upstream pin: `e6600ffc4e8e6620eeb45bf49bcdbd5e4b84163f`
- Original builder blob: `3bfe31b9bb87c7d0b7b75f62054149bfa583fb1a`
- Missing-pair fixture at pitch −85°, yaw 30°: six upstream depth failures; zero patched failures
- Flush-contact pitch sweep 50°–65°: zero swaps in both upstream and patched fixtures

These regression fixtures run official order/depth checks only. They do not replace the full-scene audit.

## Supplemental mixed-depth coverage

PASS: `node qa/explorer-mixed-depth.mjs`, exit 0, 1,278.109 seconds. The unchanged full-resolution official depth oracle checked 252 scene poses and 43,754 overlapping pairs, with zero failures. The grid contains 12 yaw angles, seven pitches including both ±85° limits, and assembled/exploded/independent-slide profiles. Evidence: `qa/explorer-mixed-depth.log` and `qa/explorer-mixed-depth.json`, including source hashes and every sampled pose. This additional check is depth-only: the other categories are explicitly skipped and inherit no new pass claim from this supplemental run.

## Bounded computational cost

A refreshed `node qa/explorer-scene-performance.mjs` comparison passed after the audit processes completed. Across 360 mixed actual-UI poses with independent slides and five measured rounds per variant, the patched median frame calculation was 1.604 ms and p95 was 2.661 ms; the upstream values were 1.549 ms and 2.437 ms. Median round-mean cost increased by about 8.0% on this host. Payload growth was 288 bytes. Both variants recorded zero forced or unseparated states. These sequential Node measurements are load-sensitive and do not measure browser frame rate.

## Limits

The stock turn-root fidelity/benchmark helper is not a valid free-root camera test. It was not misreported as coverage. The earlier exact-transform runtime fix remains in place, and its audit tolerance was not weakened.

Node geometry timings in `qa/explorer-scene-performance.json` are computational measurements, not browser FPS. Browser rendering, layout, hit testing, labels, clipping, accessibility, motion behavior and frame timing require their own UI verification. This report makes no claim that browser QA, publication, deployment, merge or release occurred.
