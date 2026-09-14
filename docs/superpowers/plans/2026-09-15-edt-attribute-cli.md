# EDT attribute evidence CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the accepted `plan_edt_attribute_three_way` read-only contract through a bounded local CLI command.

**Architecture:** Add a transport-only `edt-attribute-plan` branch to `rentgen_core.cli`. It authenticates the selected project before reading three existing metadata-tree JSON envelopes, decodes them with `_metadata_tree`, calls the public planner once, and returns its evidence through the existing `_ProposalCommandResult` redaction/size path. It has no snapshot, operation, materialization or write boundary.

**Tech Stack:** Python 3.11, argparse, existing `CoreError`, `rentgen_core.cli._metadata_tree`, pytest, Black, Ruff.

## Global Constraints

- The command requires `--registry`, `--project`, `--base-json`, `--current-json`, and `--upstream-json`.
- Input envelopes use `schema: 1`, `encoding: base64`, and a `files` mapping; paths and bytes use existing metadata-tree validation.
- Permission check for `project:read`, `source:edit`, and `analysis:run` occurs before every payload read and before output emission.
- The command is read-only evidence only: no `--snapshot`, `--operation-id`, native process, materialization, filesystem write, 1C write, or live apply.
- Limits are existing metadata-tree limits plus `--max-children`, with the planner ceilings: 256 files, 1 MiB per file, 16 MiB total per tree, 20,000 children.
- Errors remain payload-free through the current CLI `CoreError` envelope and revoked access must not leak input or result.

---

### Task 1: Add CLI parser and permission contract

**Files:**
- Modify: `rentgen_core/cli.py` parser command list and command-specific arguments
- Test: `tests/unit/test_edt_attribute_cli.py`

**Interfaces:**
- Consumes: existing `_metadata_tree`, `_proposal_input`, and public `plan_edt_attribute_three_way`.
- Produces: parsed `args.command == "edt-attribute-plan"` with three `Path` inputs and four integer limits.

- [ ] **Step 1: Write the failing parser/help tests**

Add tests that `--help` lists `edt-attribute-plan`, all three JSON options are required, repeated options raise `INVALID_ARGUMENT`, and missing options produce the existing JSON error envelope.

- [ ] **Step 2: Run the parser tests and verify failure**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_attribute_cli.py -k parser`
Expected: FAIL because the command is not registered.

- [ ] **Step 3: Register the command and exact limits**

Add the command to `_parser()` and reuse the metadata tree argument shape:

```python
elif name == "edt-attribute-plan":
    for label in ("base", "current", "upstream"):
        command.add_argument("--" + label + "-json", type=Path, required=True, action=_Once)
    for limit, ceiling in {
        "max_files": 256,
        "max_file_bytes": 1024 * 1024,
        "max_total_bytes": 16 * 1024 * 1024,
        "max_children": 20_000,
    }.items():
        command.add_argument("--" + limit.replace("_", "-"), type=int, default=ceiling, action=_Once)
```

Put the command in the `project:read`, `source:edit`, `analysis:run` permission branch with the other analysis commands, and add it to the metadata input branch only where needed for context setup.

- [ ] **Step 4: Re-run parser tests**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_attribute_cli.py -k parser`
Expected: PASS.

- [ ] **Step 5: Commit the parser boundary**

```powershell
git add rentgen_core/cli.py tests/unit/test_edt_attribute_cli.py
git commit -m "feat: register EDT attribute evidence CLI"
```

### Task 2: Implement bounded execution and negative cases

**Files:**
- Modify: `rentgen_core/cli.py` execution dispatch and helper
- Test: `tests/unit/test_edt_attribute_cli.py`

**Interfaces:**
- Consumes: parsed command and three metadata-tree envelopes.
- Produces: planner result in `_ProposalCommandResult(value, ctx, frozenset(permissions))`.

- [ ] **Step 1: Write failing execution tests**

Build the existing synthetic Catalog tree into base/current/upstream envelopes. Test a successful result equals direct `plan_edt_attribute_three_way` output, malformed/base64/path/size input is rejected, owner transfer returns a payload-free `EDT_THREE_WAY_INVALID` error, and permission revocation prevents opening any input path.

- [ ] **Step 2: Run the execution tests and verify failure**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_attribute_cli.py -k execution`
Expected: FAIL because dispatch has no `edt-attribute-plan` branch.

- [ ] **Step 3: Add a transport helper**

Implement `_edt_attribute_plan_command(args, ctx, permissions)`:

```python
def _edt_attribute_plan_command(args, ctx, permissions):
    from . import plan_edt_attribute_three_way

    limits = {name: getattr(args, name) for name in (
        "max_files", "max_file_bytes", "max_total_bytes", "max_children"
    )}
    ceilings = {"max_files": 256, "max_file_bytes": 1024 * 1024,
                "max_total_bytes": 16 * 1024 * 1024, "max_children": 20_000}
    if any(type(limits[name]) is not int or not 1 <= limits[name] <= ceilings[name]
           for name in limits):
        raise CoreError("THREE_WAY_LIMIT", "EDT attribute CLI limits are out of bounds")
    trees = [
        _metadata_tree(_proposal_input(ctx, path, _MAX_JSON_BYTES, permissions=permissions), limits)
        for path in (args.base_json, args.current_json, args.upstream_json)
    ]
    value = plan_edt_attribute_three_way(*trees, **limits)
    _proposal_permissions(ctx, permissions)
    return _ProposalCommandResult(value, ctx, frozenset(permissions))
```

Dispatch it before the generic `metadata-` branch and preserve the final permission check in `main` by returning `_ProposalCommandResult`.

- [ ] **Step 4: Run the execution tests**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_attribute_cli.py -k execution`
Expected: PASS with payload-free errors and no source writes.

- [ ] **Step 5: Commit the transport implementation**

```powershell
git add rentgen_core/cli.py tests/unit/test_edt_attribute_cli.py
git commit -m "feat: expose EDT attribute evidence over CLI"
```

### Task 3: Regression, documentation, and package verification

**Files:**
- Modify: `docs/product/EDT-ATTRIBUTE-THREE-WAY.md`, `README.md`, `pyproject.toml` only if the plan/doc is not already included
- Test: `tests/unit/test_metadata_cli.py`, `tests/unit/test_cli_contracts.py` (existing suites)

**Interfaces:**
- Consumes: committed parser and transport implementation.
- Produces: documented command with no change to metadata materialization or live apply.

- [ ] **Step 1: Document the command and its input envelope**

Add one PowerShell example using three `schema=1` base64 tree files and state explicitly that the output is read-only evidence with `coverage: partial`; link it from the README table.

- [ ] **Step 2: Run focused and CLI regressions**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_attribute_cli.py tests/unit/test_metadata_cli.py tests/unit/test_cli_contracts.py tests/unit/test_edt_attribute_three_way.py`
Expected: all pass.

- [ ] **Step 3: Run quality checks**

Run: `py -3.11 -m black --check rentgen_core/cli.py tests/unit/test_edt_attribute_cli.py`; `py -3.11 -m ruff check rentgen_core/cli.py tests/unit/test_edt_attribute_cli.py`; `py -3.11 -m compileall -q rentgen_core`; `git diff --check`.
Expected: all clean.

- [ ] **Step 4: Run the full suite and package check**

Run: `py -3.11 -m pytest -q`; `py -3.11 -m build --sdist --outdir .tmp-sdist-check`; inspect that the new contract doc appears exactly once, then remove only the created temporary archive/directory.
Expected: existing Windows symlink skips only; no new skips or failures; sdist contains module and docs.

- [ ] **Step 5: Commit the documentation and record evidence**

```powershell
git add README.md docs/product/EDT-ATTRIBUTE-THREE-WAY.md pyproject.toml
git commit -m "docs: document EDT attribute evidence CLI"
```

Update the existing product checkpoint with exact commit/tree, test totals, reviewer findings, CI run and residual limitations. Do not promote main, tag, deploy, or enable live apply.
