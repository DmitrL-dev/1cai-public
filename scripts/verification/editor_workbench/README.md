# Installed Windows workbench acceptance

This verifier executes the installed Companion VSIX in a real pinned Windows
Electron Extension Host with the exact installed Core wheel and actual pinned
BSL Language Server. It is an automated editor API test, not human GUI,
keyboard, accessibility, native1C, AI-quality or complete IDE acceptance.
Local Python/Node guard tests do not qualify the editor. A successful exact-source
`native-editor-workbench` CI job and its positive receipt are required.

The `native-editor-workbench` job depends on `windows-artifacts` and uses its
`verified-core-development` artifact. The separate `windows` job runs the full
unit contracts in parallel; the entire Product workflow must succeed before
integration. An early producer artifact does not qualify a failed or incomplete
Product run. The kit receipt must identify the actual
checkout commit (GitHub's test-merge commit on pull requests), and the triggering
PR HEAD is recorded separately. The VSIX must reproduce that same checkout.
Every installed product file is compared with the wheel and bound Git bytes.
No source checkout is placed on the installed interpreter's import path.

## Two real editor processes

1. Open the owned project; search the retained metadata descriptor and use its
   minted module handle. Create a manual draft, edit a real `TextDocument`, save
   it through the actual command and check the exact committed revision with
   real BSL-LS. Problems must identify that saved revision's URI, bytes and range.
2. An independent installed CLI commits a concurrent revision. Saving the old
   working copy must refuse CAS without retry or overwriting the buffer. Removing
   `source:edit`/`analysis:run` while retaining the fixture administrator's read
   access must block a write through actual Core authorization. A forged UI
   handle is refused separately.
3. The explicit `durable_intent_commit_unobserved` crash-stage fixture writes the
   genuine edit journal intent and commits it with the real installed CLI. Its
   receipt is not delivered to a save presenter. This models the persisted stage
   boundary; it is **not** a TCP-loss or real process-kill experiment.
4. A controlled fixture change publishes a newer snapshot while the extension
   keeps the old snapshot and historical draft revision selected.
5. A fresh Extension Host uses the same workspace URI, profile and user-data
   directory. The extension must restore its own `workspaceState`, revalidate
   the exact old snapshot/revision with Core, and reconcile the unobserved commit
   through `editResult`. Repeated inspection must preserve one history receipt
   without another save. The historical BSL result is presented without a rerun.

Each editor process tree belongs to an installed Core Windows Job Object and
must be closed before acceptance. The editor and its children receive an
explicit environment allowlist without GitHub, model, SSH or cloud credentials.
The fixture keeps its read/admin permissions to restore its temporary permission
change; it does not claim complete membership removal or Windows account isolation.

## Fixed public inputs and licenses

The complete versions, byte sizes and SHA256 pins are in `inputs.py`.
They repeat existing repository runtime pins; no `latest` download is used.

| Input | Version | License / origin |
| --- | --- | --- |
| VSCodium Windowsx64 ZIP | `1.135.06055`, editor API `1.135.0` | [Official release](https://github.com/VSCodium/vscodium/releases/tag/1.135.06055), [MIT](https://github.com/VSCodium/vscodium/blob/1.135.06055/LICENSE); all shipped license and third-party notices remain in the extracted tree |
| Temurin Windowsx64 JDK | `21.0.12.1+1` | [Official release](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.12.1%2B1), GPL2 with Classpath Exception; shipped notices retained |
| BSL Language Server | `1.0.5` | [Official release](https://github.com/1c-syntax/bsl-language-server/releases/tag/v1.0.5), LGPL3 or later; runtime metadata also lives in the installed product profile |

The editor ZIP, JDK ZIP and JAR must pass exact size/SHA verification before use.
ZIP extraction preflights all original names, aliases, duplicate/case-folding
collisions and bounds before writing any destination. The installed BSL runtime
also passes the product's own complete runtime pin verifier. Editor, JDK, Core,
scanner, VSIX and installed runtime bytes are checked again after both hosts.
Automatic editor/extension updates, telemetry and recommendations are disabled
in this owned profile. No installed system editor or runtime is changed.

The launch uses Microsoft's documented
[`--extensionDevelopmentPath` / `--extensionTestsPath`](https://code.visualstudio.com/api/working-with-extensions/testing-extension#advanced-setup-your-own-runner)
and [isolated CLI installation options](https://code.visualstudio.com/docs/configure/command-line#_working-with-extensions).
The development extension is this small test runner. The target Companion is
installed from the exact VSIX, not loaded as a development extension. No mock
`vscode` provider, network model or npm dependency is used.

## Receipts and limits

The attempt must be a new direct child `RUNNER_TEMP/rg-editor-<12 hex>`.
Only reduced `evidence/acceptance.json`, `runtime-binding.json` and supervisor
receipts are uploaded. Raw editor logs, source fixtures, full inventories and
private per-profile state stay in the disposable attempt. Receipts contain
reduced metadata and bounded Companion filenames; `full_product_ready` remains false.

An accepted first phase is saved immediately after its supervisor proves owned
process cleanup, even if restart later fails. A failed host contributes only a
closed checkpoint ID, boolean progress flags, finite error code/category/operator
and assertion value types, safe integers, sizes or string hashes. Exception
messages, stacks, object fields, source text and absolute paths are excluded.
Missing, malformed or oversized private phase receipts produce a finite
unavailable diagnostic and preserve the original process failure. Partial phase
success never changes overall `accepted:false`; both phases and the final byte
and cleanup checks remain mandatory.
Checkpoints update only the attempt's original regular, single-link acceptance
file, with identity checks and a bounded write/flush/fsync. Other input and
receipt creation stays exclusive. A terminal write failure refuses success and
cannot replace an already active host/process exception.

The installed-layout comparison includes `.vsixmanifest` with the exact bytes of
the outer VSIX `extension.vsixmanifest`. This is a source-based correction for
the [pinned editor installer](https://github.com/microsoft/vscode/blob/08d4889f9ec4a1685d257b9b95de036c8e1ce1e5/src/vs/platform/extensionManagement/node/extensionManagementService.ts#L649)
and its [prefix extraction](https://github.com/microsoft/vscode/blob/08d4889f9ec4a1685d257b9b95de036c8e1ce1e5/src/vs/base/node/zip.ts#L320),
not a positive Windows runtime receipt. Unknown files, missing files, changed
manifest bytes and other payload changes still fail. On either installed-file
inspection, `acceptance.json` records bounded relative filenames and hashes for
missing, unexpected and changed entries; it includes no file bodies or absolute
paths. Portable synthetic layout tests qualify this comparison only; actual
Windows acceptance still requires the exact-source CI receipt above.

Guard tests (portable; these do not launch Electron). The new CI job explicitly
installs the pinned tools and runs both paths before its actual runtime attempt;
the repository's default `testpaths=tests/unit` does not collect these files:

```text
python -m pip install -r requirements-test.txt
python -m pytest -q tests/integration/test_editor_workbench_archive.py tests/integration/test_editor_workbench_inputs.py
node --check scripts/verification/editor_workbench/host.cjs
node --test scripts/verification/companion_host/editor-phase.test.cjs
```

Real Windows acceptance (the CI job supplies these exact artifact inputs):

```text
python scripts/verification/editor_workbench/run.py --checkout . --kit <verified-kit.zip> --build-receipt <kit-acceptance.json> --vsix <exact-companion.vsix> --expected-commit <actual-checkout-SHA> --trigger-head <event-HEAD-SHA> --output <new-owned-attempt>
```

Commit `3cc29c2` reached actual Windows Electron execution: installation and
inventory passed, the first supervisor exited 0 with cleanup, and restart exited
1 with cleanup. Its public receipt lacks the failed private phase body, so the
restart cause remains unknown and the attempt is not accepted. New diagnostics
and later source changes require a new exact-source Windows run.
Real kill/reconnect, complete permission revocation, human UI/accessibility,
licensed1C/EDT/YAxUnit and the other IDE scenarios remain separate release gates.
