# Independent Anatomy browser qualification

Reconstructed from authored work after the execution workspace was replaced on 2026-10-13 at approximately 21:54 UTC. The earlier package was never published. No real-browser run or browser screenshots have yet been produced. Syntax checks, test discovery, jsdom and SVG renders are not browser qualification.

## Integration

Copy this package to `tests/anatomy-browser`, the builder to `tools/anatomy-atlas`, and only after maintainer review copy the candidate workflow to `.github/workflows/anatomy-browser-ci.yml`. No PR publication, workflow mutation, merge or release has been performed during preparation.

CI uses exact PR HEAD, complete Git history, Python 3.12.14 and Node 24.15.0. It regenerates source data from accepted commit 6c8feb291dd251826eebb99e145f4a39f56cda47 using the shipped stdlib-only extractor, verifies the pinned generated hashes, builds the static atlas, and serves only index.html, source-texts.json and the license on 127.0.0.1. Product modules are never imported or run. Generated data and HTML should not be committed.

Playwright 1.56.1 is locked; its lockfile was recovered directly from accepted Rentgen commit 6c8feb291dd251826eebb99e145f4a39f56cda47, tests/gui/browser/package-lock.json, changing only the package name. Install uses npm ci --ignore-scripts. Actions are pinned to the same exact first-party action SHAs used by Rentgen CI. Chromium's normal sandbox is enabled. Do not add --no-sandbox, relax AppArmor, change sysctl or elevate to get around a denied local browser launch.

## Functional gates

1. Real mouse yaw/pitch, shift-pan, wheel and button zoom; geometry markup and actual screenshot changes; explode, top/front and reset.
2. Direct solid pointer hit-testing and selection; system to file/module to declaration with directory facet separately qualified; exact source text lines and SHA-256; HTML source must remain inert text.
3. Direct dependency-stroke pointer hit-testing, direction, source references and endpoint inspection; all steps of one real source route and route overlay.
4. History, paging, directory/role/search filters, isolate and layer visibility.
5. Keyboard activation/camera controls and stable reduced-motion pixels.
6. Chromium touch emulation at 390×844: native touch orbit/pinch/tap, accessible object list and selected-object controls, exact source view, no page overflow and 40px minimum tested primary control.
7. Light/dark desktop and 1024×768 screenshots of real selected source. Font geometry is recorded, but visual readability still needs actual artifact inspection.
8. Browser input-to-two-frames timing and idle frame samples. This is CI host data, not a user-device/mobile FPS guarantee.

Normal interaction uses real mouse/keyboard/CDP touch. Read-only exposed state and repository data are only assertions, never navigation mutation hooks. Browser network is restricted to the loopback server. No trace, video, browser profile, tokens or external screenshots are retained.

## Receipts and review

The always-run receipt step records exact checkout/expected HEAD, built HTML and source payload hashes, named case outcomes and available PNG/JSON hashes even on failure. Incomplete or failed cases remain failing. Skips and retries are rejected. Automated success still records screenshot_visual_review: pending until screenshots are actually opened and reviewed. Case count or changed pixels alone do not establish useful readable design.

The intended route is isolated GitHub browser qualification. The local cloud's prior Chromium EPERM was not retried or bypassed. Private Site access and audience remain unchanged. No user's Mac or unrelated product work is involved.
