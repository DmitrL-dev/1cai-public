# Model context memory implementation plan

> For agentic workers: implement the independent Python and Companion slices with Source-only subagents and Root-executed verifiers. Track steps below.

**Goal:** Carry an explicit prepared-profile context to the one local model request and retain proof of the value.

**Architecture:** The prepared profile owns `context_tokens`. Companion journals it and passes a CLI equality assertion; Python validates the profile and emits exact wire/metrics values. Reduced contexts have a complete-request byte guard; the legacy default remains compatible.

**Tech Stack:** Python 3.11, existing anyio/httpx, Node Companion, pytest and node:test. No new dependencies.

## Global constraints

- Values are exactly 8192, 16384, 32768; missing profile value resolves to 32768.
- `num_predict=4096`, `keep_alive=0`, timeout and one-request policy remain unchanged.
- Reduced-context request bytes must fit `context_tokens - 4096 - 512`; this is not exact token accounting for arbitrary models.
- Existing C7/D9 evidence is immutable. New native qualification requires new Source/install/profile evidence.

## Task 1: Python transport and profile assertion

Files: `integrations/open-editor/repair_model.py`, `run_repair.py`; tests `tests/unit/test_local_repair_model.py`, `test_repair_profile.py`.

Interface: `OllamaEditor(..., context_tokens=32768)`; `validate_context_tokens(value)->int`; `validate_profile(..., expected_context_tokens=None)->int`.

- [x] Add tests for resolution and exact UTF-8 boundary; run them and record six expected failures.
- [x] Implement strict integer validation, profile/CLI equality and request metrics. The guard is:

```python
if self.context_tokens < 32768 and len(raw) > self.context_tokens - 4096 - 512:
    raise ValueError("MODEL_CONTEXT_INPUT_LIMIT")
```

- [x] Run `pytest -q tests/unit/test_local_repair_model.py tests/unit/test_repair_profile.py`; expected all pass, fixture HTTP only.

## Task 2: New-profile preparation

Files: `integrations/open-editor/prepare.py`; tests `tests/unit/test_open_editor_profile.py`.

Interface: `prepare(..., context_tokens=32768)` and `--context-tokens` with three integer choices. Store the integer in new profile JSON and `str(context_tokens)` in Cline's `ollamaApiOptionsCtxNum` when an Ollama model is selected.

- [x] Add default/explicit/invalid-before-output tests; Root runs selected nodes and verifies missing behavior.
- [x] Validate before output creation; write both matching settings without importing model runtime dependencies.
- [x] Root runs the changed profile test file; expected all pass.

## Task 3: Companion propagation and reconciliation

Files: `lib/core.cjs`, `lib/repair.cjs`, `test/core.test.cjs`, `test/repair.test.cjs` under `integrations/vscode-rentgen`.

Interface: `profileConfig` retains frozen numeric `context_tokens`; each new request persists it and passes `--context-tokens` to Python. Analysis status requires new report `model.num_ctx` equality; old requests without the field remain readable.

```javascript
const context = Object.hasOwn(value, 'context_tokens') ? value.context_tokens : 32768;
requireValue(Number.isInteger(context) && [8192,16384,32768].includes(context), 'INVALID_EDITOR_PROFILE');
```

- [x] Add retention/validation, argv/journal and mismatch/legacy tests; Root proves selected failures.
- [x] Implement this contract in existing functions; no replay or new process policy.
- [x] Root runs `node --test integrations/vscode-rentgen/test/core.test.cjs integrations/vscode-rentgen/test/repair.test.cjs`; expected all pass.

## Task 4: Documentation, packaging and Git

- [x] Document exact values, conservative byte limit and new-profile procedure in adapter and local-repair documentation.
- [x] Bump Companion to 0.1.17; verify the same source builds identical VSIX bytes and bundled adapter bytes match source.
- [ ] Review the complete diff, run the relevant packaging gate and commit/push a `codex/` branch with a detailed GitHub announcement and PR.
- [ ] Admit only actual passing CI and installed bytes. Native/general-model/release/deployment claims stay false until their separate evidence exists.

## Task 5: Daily harness binding

- [x] Prepare new daily profile and scenario with strict matching context before filesystem/process activity (18 RED failures; 26 GREEN tests).
- [x] Bind complete profile/scenario bytes in wrapper inputs and before/after receipts, retaining drift even on editor wait errors (19 RED failures plus two size refusals; 28 GREEN tests).
- [x] Prove the host checks context and profile bytes before activation, then exact saved request/report context before native TestDraft (34 RED failures; 167 GREEN host/semantic tests).
- [ ] Obtain independent review and publish the verified Source candidate.

Local HTTP fixtures and constructed editor mocks are not model/native or RAM/VRAM qualification.
