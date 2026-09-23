# EDT identity three-way planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure, bounded, read-only three-way planner for EDT identity inventories and expose it through an authenticated local CLI without enabling configuration writes.

**Architecture:** Keep identity comparison in a new `rentgen_core/edt_identity_three_way.py` module. The module accepts normalized inventory mappings and returns deterministic identity/owner/layer evidence; it never opens files or calls 1C/EDT. A separate CLI adapter reads three bounded JSON inventory objects, authenticates `project:read` around every file/result/error boundary, and emits only a size-bounded JSON envelope.

**Tech Stack:** Python 3.11, `dataclasses`, strict `json` parsing already used by `rentgen_core.cli`, `pytest`, Black, Ruff, existing `CoreError` and three-way action helpers.

## Global Constraints

- Inputs are UTF-8 inventory objects copied unchanged from `edt-inventory.result`; they use `parser: edt_identity_v1` and are not metadata-tree/base64 envelopes.
- Base, current and upstream snapshot IDs may differ; project IDs, identity bindings and source references must validate per version.
- Identity key is `(layer.layer_id, canonical_uuid)`; type, owner UUID, owner path and layer changes fail closed as `unsupported`.
- Actions are exactly `unchanged`, `same_change`, `keep_current`, `take_upstream`, `conflict`, and `unsupported`.
- The result is `schema: 1`, `scope: edt-identity-v1`, `mode: read_only`, `coverage: partial`, `materialization: unavailable`, and `native_validation: unavailable`.
- No XML/property/form/СКД payload, filesystem write, snapshot creation, native call, or apply/materialize operation is allowed.
- All limits are positive integers and may only lower fixed ceilings; serialized output is capped at 8 MiB with no partial output.
- The accepted candidate requires the full local suite, static checks, exact sdist byte/content checks, independent Astra xhigh review, and the exact Windows Product CI run.

---

### Task 1: Pure inventory normalization and three-way planner

**Files:**
- Create: `rentgen_core/edt_identity_three_way.py`
- Modify: `rentgen_core/__init__.py` to export `plan_edt_identity_three_way` and its limits type using the existing public-export style
- Test: `tests/unit/test_edt_identity_three_way.py`

**Interfaces:**
- Consumes: three `Mapping[str, object]` inventory objects and keyword-only `limits: EDTIdentityThreeWayLimits | None`.
- Produces: `plan_edt_identity_three_way(base, current, upstream, *, limits=EDTIdentityThreeWayLimits()) -> dict` and `EDTIdentityThreeWayLimits` with explicit ceilings for input bytes, objects, owners, layers and result rows.

- [ ] **Step 1: Write failing tests for valid identity actions.**

  Build minimal inventory factories in `tests/unit/test_edt_identity_three_way.py` with one root object and one direct child, distinct snapshot IDs but the same project ID. Assert unchanged, same-change, current-only, upstream-only and conflict actions; assert deterministic ordering and exact result metadata. Add addition, retained-owner deletion and rename cases.

- [ ] **Step 2: Run the new tests and verify the import/API fails.**

  Run: `py -3.11 -m pytest -q tests/unit/test_edt_identity_three_way.py`

  Expected: collection fails because `rentgen_core.edt_identity_three_way` and its public export do not exist.

- [ ] **Step 3: Implement strict limits and normalization.**

  Define a frozen dataclass whose `__post_init__` rejects non-`int`, boolean, zero, negative and above-ceiling values with `CoreError("INVALID_QUERY_OPTIONS", ...)`. Normalize each envelope once: validate `parser == "edt_identity_v1"`, `coverage == "partial"`, `identity_scope`, `owner_basis`, `layer_basis`, project ID, snapshot reference shape, the actual `SnapshotLayer` fields (`layer_id`, `ordinal`, `kind`, `configuration_uuid`, `identity_status`, `source_format`) plus inventory counts, and object records; canonicalize UUIDs and SHA-256 strings; reject duplicate `(layer_id, uuid)` keys, missing owner/layer/source evidence, unknown fields that can hide identity data, malformed hashes and non-finite sizes. The producer has no source byte size, so normalize `source_size_bytes` to `None`; never infer a size. Record each input’s exact canonical digest and retain no payload beyond identity evidence.

- [ ] **Step 4: Implement action and unsupported semantics.**

  Reuse the existing pure `_action` helper only after constructing immutable canonical projections. Compare union keys by `(layer_id, canonical_uuid)`. Emit `unsupported` reason codes for layer/type/owner UUID changes, divergent owner paths, incomplete retained-owner evidence, and UUID reuse. Emit deletion only when that version retains the owning object/layer evidence. Sort rows by layer ordinal, layer ID and UUID; include bounded counts and per-version evidence without XML/property data.

- [ ] **Step 5: Run valid tests and add negative tests.**

  Run: `py -3.11 -m pytest -q tests/unit/test_edt_identity_three_way.py`

  Add and pass cases for project mismatch, malformed snapshot, foreign source reference, duplicate identities, duplicate owners/layers, non-partial coverage, owner/type/layer moves, incomplete deletion evidence, NaN/boolean sizes, limit overflow, and mutable mapping drift. Assert no source payload or private diagnostic appears in returned errors.

- [ ] **Step 6: Run focused static checks and commit the pure module.**

  Run: `py -3.11 -m black --check rentgen_core/edt_identity_three_way.py tests/unit/test_edt_identity_three_way.py; py -3.11 -m ruff check rentgen_core/edt_identity_three_way.py tests/unit/test_edt_identity_three_way.py; py -3.11 -m compileall -q rentgen_core; git diff --check`

  Commit: `git add rentgen_core/edt_identity_three_way.py rentgen_core/__init__.py tests/unit/test_edt_identity_three_way.py && git commit -m "feat: add bounded EDT identity three-way planner"`

### Task 2: Read-only CLI adapter and authorization regressions

**Files:**
- Modify: `rentgen_core/cli.py` parser, permission dispatch and `_execute`
- Test: `tests/unit/test_edt_identity_three_way_cli.py`

**Interfaces:**
- Consumes: `plan_edt_identity_three_way`, `_proposal_input`, `_ProposalCommandResult`, and `project:read` state context.
- Produces: `rentgen edt-inventory-plan --registry PATH --project ID --base-json PATH --current-json PATH --upstream-json PATH` with bounded limit options and one JSON result envelope.

- [ ] **Step 1: Write failing parser and dispatch tests.**

  Assert required registry/project/three input files, repeated-option rejection, typed positive lower-only limits, absence of `--apply`, `--output`, `--workspace`, `--operation-id`, `--snapshot`, `--source-root` and native profile options, `project:read` permission selection, and one call to the pure planner with parsed mappings.

- [ ] **Step 2: Run the new CLI tests and verify they fail.**

  Run: `py -3.11 -m pytest -q tests/unit/test_edt_identity_three_way_cli.py`

  Expected: parser does not recognize `edt-inventory-plan` and the adapter import is absent.

- [ ] **Step 3: Add strict JSON input decoding before implementation dispatch.**

  Add a dedicated decoder in `cli.py` or the planner module that reads at most 8 MiB per file through `_proposal_input(ctx, path, 8 * 1024 * 1024, permissions={"project:read"})`, rejects invalid UTF-8, duplicate keys, constants, trailing data and non-object values, then passes the three normalized mappings to the pure planner. Do not reuse `_metadata_tree`, because inventory objects are not base64 trees.

- [ ] **Step 4: Add command dispatch and payload-free result handling.**

  Add `_EDT_IDENTITY_THREE_WAY_LIMITS`, parser options, the `edt-inventory-plan` read-only permission branch, and a dedicated `_edt_identity_three_way_command`. Wrap planner `CoreError` with a fixed message and empty details. Return `_ProposalCommandResult(..., output_limit=8 * 1024**2)` so `main()` rechecks rights before serialization and after serialization. Set `proposal_scope.context` to the snapshot-free authenticated state context before any file read, preserving reauthorization on errors.

- [ ] **Step 5: Add security and regression tests.**

  Cover revocation before each input, after each input, during planner normalization, before result serialization, after result serialization, and before error emission; assert no partial result, no `PRIVATE_PAYLOAD`, and no subsequent file read after revocation. Cover output cap, unsupported options, malformed JSON, planner error redaction, mapping drift, and all existing CLI command sets.

- [ ] **Step 6: Run focused and adjacent checks and commit the CLI.**

  Run: `py -3.11 -m pytest -q tests/unit/test_edt_identity_three_way_cli.py tests/unit/test_edt_inventory_cli.py tests/unit/test_edt_attribute_cli.py tests/unit/test_metadata_cli.py tests/unit/test_metadata_materialize_cli.py tests/unit/test_project_core_cli.py tests/unit/test_project_core_cli_options.py; py -3.11 -m black --check rentgen_core/cli.py tests/unit/test_edt_identity_three_way_cli.py; py -3.11 -m ruff check rentgen_core/cli.py tests/unit/test_edt_identity_three_way_cli.py; git diff --check`

  Commit: `git add rentgen_core/cli.py tests/unit/test_edt_identity_three_way_cli.py && git commit -m "feat: expose EDT identity three-way CLI"`

### Task 3: Product documentation, packaging and final qualification

**Files:**
- Create: `docs/product/EDT-IDENTITY-THREE-WAY.md`
- Modify: `README.md`, `ROADMAP.md`, `docs/product/AUDIT-20260912.md`, `docs/product/READINESS.md`, `pyproject.toml` only if the existing sdist allowlist requires the new product document/module
- Test/verification: existing full suite and packaging scripts; no new harness

**Interfaces:**
- Consumes: the stable planner/CLI contracts from Tasks 1–2.
- Produces: user-facing contract docs with explicit partial coverage and evidence-backed limits.

- [ ] **Step 1: Document the input/output contract and examples.**

  Explain how to save the `result` object from `edt-inventory`, run the three-way command, interpret action/reason codes, and why differing snapshot IDs are expected. State the no-write/no-native boundary, all limits, 8 MiB cap and revocation behavior. Link the document from README, ROADMAP, AUDIT and READINESS without claiming live update readiness.

- [ ] **Step 2: Run documentation and packaging checks.**

  Run: `git diff --check; py -3.11 -m compileall -q rentgen_core; py -3.11 -m build --sdist --outdir C:\1cAI\output\edt-identity-three-way-sdist`

  Verify exactly one copy of `rentgen_core/edt_identity_three_way.py`, `rentgen_core/cli.py` and `docs/product/EDT-IDENTITY-THREE-WAY.md` in the archive, and byte-compare each to the working tree. Internal plan/spec files remain excluded from the product archive.

- [ ] **Step 3: Run the complete local qualification.**

  Run: `py -3.11 -m pytest -q`

  Record the exact collected/passed/skipped counts and skip reasons; do not treat environment errors as skips. Repeat the impacted CLI/planner/security subset after any change.

- [ ] **Step 4: Commit the documentation/package changes.**

  Commit: `git add README.md ROADMAP.md docs/product/AUDIT-20260912.md docs/product/READINESS.md docs/product/EDT-IDENTITY-THREE-WAY.md pyproject.toml && git commit -m "docs: qualify EDT identity three-way contract"`

- [ ] **Step 5: Independent release review and correction loop.**

  Give the exact full release diff from the previous public candidate to an Astra xhigh reviewer who did not author the change. Require findings with location, contract, scenario, consequence, evidence and minimal fix. If any P0–P3 is found, return the fix to the same implementer, rerun affected/full checks and repeat review.

- [ ] **Step 6: Push only the accepted development branch and verify CI.**

  After review approval and a clean tree, run `git push public codex/edt-metadata-dev9`. Verify the push-triggered Windows Product CI run for the exact commit, job summary, duration and artifacts. Do not promote to `public/main`, tag, publish a release or deploy production.
