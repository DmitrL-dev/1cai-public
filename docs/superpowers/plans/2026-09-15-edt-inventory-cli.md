# EDT Identity Inventory CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the bounded snapshot-only EDT identity inventory through a secure local CLI command.

**Architecture:** Add a dedicated `edt-inventory` parser/dispatch branch in `rentgen_core/cli.py`. The adapter constructs typed `EDTInventoryLimits`, resolves one explicit snapshot through the existing graph factory, calls `edt_metadata_inventory` exactly once, and returns `_ProposalCommandResult` so output sizing and final authorization reuse the existing path. Existing inventory and metadata library code remains unchanged.

**Tech Stack:** Python 3.11, argparse, dataclasses, pytest, existing `LocalRuntime`, `ContextResolver`, `edt_inventory`, Windows snapshot reader.

## Global Constraints

- The command requires `--registry`, `--project`, and `--snapshot`; `--layer-id` is optional.
- The command requires only `project:read` and never accepts write, native, operation, workspace, or caller-file options.
- Limits are positive bounded integers and may be lowered but never raised above `EDTInventoryLimits` maxima.
- No partial identity rows are emitted; serialized output is capped at 8 MiB before stdout.
- Rights are checked before snapshot resolution, by the shared read session before source bytes, after serialization, and while emitting failures.
- Planner/library errors retain only stable codes and a fixed payload-free CLI message/details.
- No live 1C/EDT/Spectorn calls, source writes, materialization, watcher scheduling, or new dependencies.

---

### Task 1: Parser and read-only execution adapter

**Files:**
- Modify: `rentgen_core/cli.py` parser command list and `_execute` dispatch
- Test: `tests/unit/test_edt_inventory_cli.py`

**Interfaces:**
- Consumes: `rentgen_core.edt_inventory.EDTInventoryLimits` and `edt_metadata_inventory(ctx, layer_id=None, limits=...)`.
- Produces: `_ProposalCommandResult(value, resolved_ctx, frozenset({"project:read"}), output_limit=8 * 1024**2)` from `edt-inventory`.

- [ ] **Step 1: Write parser and execution tests first**

Add tests that assert `edt-inventory` requires explicit snapshot, parses all nine limit options with library defaults, rejects repeated/unsupported write options, checks limits before `LocalRuntime.resolve`, invokes the library once with the selected layer and typed limits, and returns the unchanged inventory envelope. Add a Windows `LocalRuntime` fixture with a published synthetic EDT snapshot and monkeypatch `cli.current_windows_principal`.

```python
def test_parser_has_snapshot_and_typed_inventory_limits():
    parsed = cli._parser().parse_args(arguments())
    assert parsed.command == "edt-inventory"
    assert parsed.snapshot == "s" * 64
    assert parsed.max_mdo_files == 2048
    assert parsed.max_identities == 20_000
    assert parsed.layer_id is None
    assert not hasattr(parsed, "operation_id")

def test_limits_are_rejected_before_snapshot_resolution(local, monkeypatch):
    monkeypatch.setattr(LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("resolved"))
    code, output = local.call("--max-identities", "20001")
    assert code == 2
    assert output["error"]["code"] == "INVALID_QUERY_OPTIONS"

def test_execution_calls_inventory_once_with_layer(local, monkeypatch):
    from rentgen_core import edt_inventory

    calls = []
    monkeypatch.setattr(
        edt_inventory,
        "edt_metadata_inventory",
        lambda *a, **kw: calls.append((a, kw)) or {"coverage": "partial"},
    )
    code, output = local.call("--layer-id", "base", "--max-identities", "17")
    assert code == 0
    assert output["result"] == {"coverage": "partial"}
    assert calls[0][1]["layer_id"] == "base"
    assert calls[0][1]["limits"].max_identities == 17
```

- [ ] **Step 2: Run the new parser tests to verify the missing command fails**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_inventory_cli.py`

Expected: FAIL because `edt-inventory` and its dispatch do not exist yet.

- [ ] **Step 3: Add bounded parser options and the adapter**

Add `edt-inventory` to `_parser()` with `--snapshot`, optional `--layer-id`, and these defaults/ceilings: `max_xml_bytes=4*1024**2`, `max_nodes=50_000`, `max_depth=64`, `max_inventory=20_000`, `max_collection=200`, `max_total_bytes=64*1024**2`, `max_asset_bytes=16*1024**2`, `max_mdo_files=2048`, `max_identities=20_000`. Implement:

```python
def _edt_inventory_command(args, runtime, principal, ctx, permissions):
    from .edt_inventory import EDTInventoryLimits, edt_metadata_inventory

    values = {name: getattr(args, name) for name in _EDT_INVENTORY_LIMITS}
    limits = EDTInventoryLimits(**values)
    _proposal_permissions(ctx, permissions)
    runtime = replace(
        runtime,
        graph_reader_factory=runtime.graph_reader_factory or _graph_factory(),
    )
    selected = runtime.resolve(principal, args.project, args.snapshot)
    if selected.sources is None:
        raise CoreError("SNAPSHOT_REQUIRED", "A published project snapshot is required")
    value = edt_metadata_inventory(selected, layer_id=args.layer_id, limits=limits)
    return _ProposalCommandResult(
        value, selected, frozenset(permissions), output_limit=8 * 1024**2
    )
```

Keep `cli.py`'s existing payload-free error wrapper in `main`; set
`proposal_scope.context` first to the snapshot-free authenticated context and
update it to `selected` before any snapshot source read. Add `edt-inventory` to
the read-only permission set (`{"project:read", "source:edit", "analysis:run"}`
must not be used; this command is `{"project:read"}`). Dispatch it before the
generic `metadata-*` branch.

- [ ] **Step 4: Run parser and execution tests**

Run: `py -3.11 -m pytest -q tests/unit/test_edt_inventory_cli.py`

Expected: all new parser/authorization/execution tests pass.

- [ ] **Step 5: Commit the bounded code and tests**

```bash
git add rentgen_core/cli.py tests/unit/test_edt_inventory_cli.py
git commit -m "feat: expose EDT identity inventory over CLI"
```

### Task 2: Negative security and regression coverage

**Files:**
- Modify: `tests/unit/test_edt_inventory_cli.py`
- Test: `tests/unit/test_metadata_cli.py`, `tests/unit/test_metadata_materialize_cli.py`, `tests/unit/test_project_core_cli.py`, `tests/unit/test_project_core_cli_options.py`

**Interfaces:**
- Consumes: the Task 1 command and existing `main`/`_emit_error` authorization behavior.
- Produces: evidence that revocation and malformed input cannot leak source details or partial inventory.

- [ ] **Step 1: Add negative scenarios**

Cover missing/foreign snapshot, missing layer, every missing `project:read` permission, revocation before resolve, revocation during the shared read session, revocation after serialization, malformed/duplicate/foreign UUID documents, limit values `0`, negative, boolean and above-ceiling, output over 8 MiB, and unsupported `--output`, `--apply`, `--operation-id`, `--workspace`, `--profile-id` and `--base-json` options. Assert code `2`, no `result` on failure, and no sentinel source payload in serialized output.

- [ ] **Step 2: Run focused security and adjacent regressions**

Run:

```powershell
py -3.11 -m pytest -q tests/unit/test_edt_inventory_cli.py tests/unit/test_edt_inventory_metadata.py tests/unit/test_edt_inventory_fixture.py tests/unit/test_metadata_cli.py tests/unit/test_metadata_materialize_cli.py tests/unit/test_project_core_cli.py tests/unit/test_project_core_cli_options.py
```

Expected: all focused tests pass; existing metadata command output shapes remain unchanged.

- [ ] **Step 3: Commit negative coverage**

```bash
git add tests/unit/test_edt_inventory_cli.py
git commit -m "test: harden EDT inventory CLI authorization"
```

### Task 3: Contract documentation, packaging and complete qualification

**Files:**
- Modify: `docs/product/EDT-INVENTORY-IDENTITY.md`, `README.md`, `ROADMAP.md`, `docs/product/READINESS.md`, `docs/product/AUDIT-20260912.md`, `pyproject.toml` if the new design/plan docs are not already in the sdist allowlist

**Interfaces:**
- Consumes: final `edt-inventory` CLI behavior and test counts from Tasks 1–2.
- Produces: documented local command, explicit read-only bounds and reproducible package contents.

- [ ] **Step 1: Document the CLI contract**

Add a Local CLI section to `EDT-INVENTORY-IDENTITY.md` with a concrete command using an explicit snapshot, layer option, all limit names, 8 MiB output cap, `project:read` authorization, fail-closed errors and no write/native options. Link it from the README table and state in ROADMAP/READINESS/AUDIT that identity evidence is transport-accessible while coverage remains partial.

- [ ] **Step 2: Run static checks and the full suite**

Run:

```powershell
py -3.11 -m black --check rentgen_core/cli.py tests/unit/test_edt_inventory_cli.py
py -3.11 -m ruff check rentgen_core/cli.py tests/unit/test_edt_inventory_cli.py
py -3.11 -m compileall -q rentgen_core
git diff --check
py -3.11 -m pytest -q
```

Expected: static checks pass; full suite passes with only the three known Windows symlink-permission skips.

- [ ] **Step 3: Verify sdist contents in an isolated temporary directory**

Run `py -3.11 -m build --sdist --outdir C:\\1cAI\\output\\edt-inventory-sdist` and inspect the archive with Python `tarfile`. Assert `rentgen_core/cli.py`, `rentgen_core/edt_inventory.py` and `docs/product/EDT-INVENTORY-IDENTITY.md` each occur exactly once and their bytes match the working tree. Internal design and plan files stay outside the product archive. After the assertions pass, remove only the exact archive and `C:\\1cAI\\output\\edt-inventory-sdist` directory, after checking both resolved paths are inside `C:\\1cAI\\output`.

- [ ] **Step 4: Commit documentation and package updates**

```bash
git add docs/product/EDT-INVENTORY-IDENTITY.md README.md ROADMAP.md docs/product/READINESS.md docs/product/AUDIT-20260912.md pyproject.toml
git commit -m "docs: publish EDT identity inventory CLI contract"
```

- [ ] **Step 5: Record the exact local candidate for independent review**

Record `git rev-parse HEAD`, `git rev-parse 'HEAD^{tree}'`, focused/full test counts, static results and sdist evidence. Request an independent GPT-6 Astra xhigh review of the complete diff relative to the previous public candidate before pushing.
