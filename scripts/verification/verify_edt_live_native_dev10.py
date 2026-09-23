"""Verify a fresh real EDT preview through installed Core dev10, 1C and undo."""

import argparse
import asyncio
import json
from pathlib import Path
import shutil
from uuid import uuid4

import rentgen_core as api
from rentgen_core import (
    metadata_apply,
    metadata_live_apply,
    metadata_plans,
    metadata_runs,
)
from rentgen_core.edt_inventory import exported_inventory
from rentgen_core.edt_profiles import get_profile
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import current_windows_principal
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.platform_check import _pin_inputs
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

import verify_metadata_migration as migration
from verify_metadata_live_native import (
    check_native_source,
    check_release,
    digest,
    require,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "packaging/fixtures/edt-metadata-v1"
PROJECT_ID = "0c48f2e6-3ee8-4bcf-b125-bb0f7bace00d"
SNAPSHOT_ID = "a68d2bafba7f708242c24eca77fad90ed3d10e941b945e54380eb035635c0982"
PROFILE_ID = "3793eb256630db189da191959de56157bc90df220f0fd4dc5afe843b1fb6446b"
PRIOR_OPERATION = "976f3251-43fe-4b7a-bdf8-0a5415fc866c"
PRIOR_PREVIEW = "31ab5c6d1c57dc3a269f48481732b4717a8140ba20b4c6fefe2643f98a09c8fe"
if not __debug__:
    raise RuntimeError("Verification requires assertions; do not use Python -O")


def fixture_inventory():
    manifest = json.loads((FIXTURE / "manifest.json").read_text("utf-8"))["files"]
    actual = {
        path.relative_to(FIXTURE).as_posix(): digest(path)
        for phase in ("baseline", "created", "renamed")
        for path in (FIXTURE / phase).rglob("*")
        if path.is_file()
    }
    require(actual == manifest, "Owned EDT fixture differs from accepted manifest")
    return {
        name.removeprefix("created/"): value
        for name, value in manifest.items()
        if name.startswith("created/")
    }


def open_owned_profile(folder):
    folder = folder.resolve(strict=True)
    require(folder.name == "profile-1", "Expected owned experimental profile")
    principal = current_windows_principal()
    registry = api.ProjectRegistry(folder / "registry.sqlite3")
    projects = registry.list_for(principal)
    require(
        len(projects) == 1 and projects[0].project_id == PROJECT_ID,
        "Owned project identity differs",
    )
    runtime = LocalRuntime(
        registry.path, graph_reader_factory=RentgenGraphReaderFactory()
    )
    ctx = runtime.resolve(principal, PROJECT_ID, SNAPSHOT_ID)
    require(
        ctx.source_root.resolve() == (folder / "source").resolve()
        and ctx.state.path.parent.resolve() == (folder / "state").resolve(),
        "Registered source or state is outside owned profile",
    )
    require(
        api.get_project_head(ctx).snapshot == ctx.snapshot,
        "Owned snapshot is not current head",
    )
    require(get_profile(ctx, PROFILE_ID)["enabled"], "EDT profile is disabled")
    prior = metadata_runs.get_preview(ctx, PRIOR_OPERATION)
    require(
        prior["preview_id"] == PRIOR_PREVIEW and prior["profile_id"] == PROFILE_ID,
        "Historical real EDT preview identity differs",
    )
    prior_run = metadata_runs.run_path(ctx, PRIOR_OPERATION)
    old_request = json.loads((prior_run / "runtime-request.json").read_text("utf-8"))
    plan = metadata_plans.create_plan(ctx, old_request["plan"]["request"])
    require(
        plan["plan_id"] == old_request["plan"]["plan_id"] == prior["plan_id"],
        "Fresh plan differs from accepted EDT plan",
    )
    original = exported_inventory(ctx.source_root, authorize=lambda: None)
    expected = fixture_inventory()
    require(
        {row["path"]: row["sha256"] for row in original} == expected
        and original == prior["preview"]["inventories"]["original"],
        "Live source differs from the owned original fixture",
    )
    return ctx, plan, original


def runtime_evidence(run):
    closed = json.loads((run / "runtime-closed.json").read_text("utf-8"))
    initialize = json.loads((run / "initialize.json").read_text("utf-8"))
    require(
        closed["status"] == "closed"
        and initialize["serverInfo"]["name"] == "edt-mcp-server",
        "EDT runtime did not close cleanly",
    )
    entries, calls = [], []
    for path in sorted(run.glob("[0-9][0-9][0-9]-request.json")):
        stem = path.name[:3]
        outcome_path = run / (stem + "-outcome.json")
        response_path = run / (stem + "-response.json")
        require(
            outcome_path.is_file() and response_path.is_file(),
            "Incomplete EDT call transcript",
        )
        request = json.loads(path.read_text("utf-8"))
        outcome = json.loads(outcome_path.read_text("utf-8"))
        calls.append({"tool": request["tool"], "status": outcome["status"]})
        for item in (path, outcome_path, response_path):
            entries.append(
                {"path": item.name, "size": item.stat().st_size, "sha256": digest(item)}
            )
    require(
        calls
        and all(
            any(call == {"tool": tool, "status": "response_received"} for call in calls)
            for tool in (
                "import_configuration_from_xml",
                "rename_metadata_object",
                "export_configuration_to_xml",
            )
        ),
        "EDT transcript lacks required successful operations",
    )
    for name in ("initialize.json", "runtime-request.json", "runtime-closed.json"):
        path = run / name
        entries.append(
            {"path": name, "size": path.stat().st_size, "sha256": digest(path)}
        )
    return {
        "server": initialize["serverInfo"]["name"],
        "server_version": initialize["serverInfo"]["version"],
        "calls": calls,
        "files": sorted(entries, key=lambda row: row["path"]),
    }


def verify(args):
    release = check_release(
        args.release_zip.resolve(strict=True),
        args.release_sha256,
        args.scanner.resolve(strict=True),
    )
    platform, ibcmd, cfe = [
        path.resolve(strict=True) for path in (args.platform, args.ibcmd, args.cfe)
    ]
    require(digest(platform) == args.platform_sha256, "1C executable SHA256 mismatch")
    require(digest(ibcmd) == args.ibcmd_sha256, "ibcmd SHA256 mismatch")
    owned = args.owned_profile.resolve(strict=True)
    output = args.output.resolve()
    require(
        not output.is_relative_to(owned) and not owned.is_relative_to(output),
        "Output overlaps owned profile",
    )
    ctx, plan, before = open_owned_profile(owned)
    output.mkdir(parents=True, exist_ok=False)
    (output / "local-inputs.json").write_bytes(
        canonical_bytes(
            {
                "owned_profile": str(owned),
                "core_module": str(Path(api.__file__).resolve()),
                "release_zip": str(args.release_zip.resolve()),
                "scanner": str(args.scanner.resolve()),
                "platform": str(platform),
                "ibcmd": str(ibcmd),
                "cfe": str(cfe),
            }
        )
    )

    preview_operation = str(uuid4())
    preview = asyncio.run(
        metadata_runs.create_preview(ctx, plan, PROFILE_ID, preview_operation)
    )
    require(
        metadata_runs.get_preview(ctx, preview_operation) == preview,
        "Fresh EDT preview readback differs",
    )
    run = metadata_runs.run_path(ctx, preview_operation)
    runtime = runtime_evidence(run)
    require(
        exported_inventory(ctx.source_root, authorize=lambda: None) == before,
        "EDT preview changed live source",
    )
    candidate = preview["preview"]["inventories"]["candidate"]
    operation = str(uuid4())
    preflight = metadata_apply.preflight_apply(
        ctx,
        preview_operation,
        operation,
        expected_preview_id=preview["preview_id"],
        expected_head=api.get_project_head(ctx),
    )
    require(
        preflight["status"] == "unavailable"
        and preflight["live_source_written"] is False,
        "Read-only preflight contract changed",
    )
    applied = metadata_live_apply.apply_live(ctx, operation)
    try:
        after = exported_inventory(ctx.source_root, authorize=lambda: None)
        require(after == candidate, "Live source differs from fresh EDT candidate")
        with _pin_inputs(ctx.source_root, after):
            native = check_native_source(
                ctx.source_root, output / "native", platform, args.platform_sha256
            )
            require(
                exported_inventory(ctx.source_root, authorize=lambda: None) == after,
                "Live source changed during native import",
            )
    finally:
        undone = metadata_live_apply.undo_live(ctx, operation)
    restored = exported_inventory(ctx.source_root, authorize=lambda: None)
    require(restored == before, "CAS undo did not restore source inventory")
    (output / "live-native.json").write_bytes(
        canonical_bytes(
            {
                "preview_id": preview["preview_id"],
                "operation_id": operation,
                "apply_status": applied["status"],
                "undo_status": undone["status"],
                "inventories": {
                    "original": before,
                    "applied": after,
                    "restored": restored,
                },
                "native": native,
            }
        )
    )

    local_data = output / "RentgenMigrationData.bsl"
    shutil.copyfile(migration.DATA, local_data)
    migration.DATA = local_data
    business = migration.verify(
        argparse.Namespace(
            input_run=run,
            output=output / "business",
            platform=platform,
            platform_sha256=args.platform_sha256,
            ibcmd=ibcmd,
            ibcmd_sha256=args.ibcmd_sha256,
            cfe=cfe,
        )
    )
    require(
        business["source_inventories"]
        == {
            "original": preview["preview"]["inventories"]["original"],
            "normalized": preview["preview"]["inventories"]["baseline"],
            "renamed": candidate,
        },
        "YAxUnit inventories differ from fresh EDT preview",
    )
    result = {
        "schema": 1,
        "source": "installed public Core dev10 with fresh real EDT/MCP preview on owned fixture",
        "release": release,
        "platform_sha256": args.platform_sha256,
        "ibcmd_sha256": args.ibcmd_sha256,
        "engine_cfe_sha256": digest(cfe),
        "project_id": PROJECT_ID,
        "snapshot_id": SNAPSHOT_ID,
        "profile_id": PROFILE_ID,
        "preview_operation_id": preview_operation,
        "preview_id": preview["preview_id"],
        "runtime": runtime,
        "operation_id": operation,
        "preflight_status": preflight["status"],
        "apply_status": applied["status"],
        "live_source_written": applied["live_source_written"],
        "changed_paths": applied["changed_paths"],
        "native": native,
        "undo_status": undone["status"],
        "inventories": {"original": before, "applied": after, "restored": restored},
        "inventory_digests": {
            "original": sha256(canonical_bytes(before)),
            "applied": sha256(canonical_bytes(after)),
            "restored": sha256(canonical_bytes(restored)),
        },
        "business_reports": {
            name: {"status": row["status"], "counts": row["counts"]}
            for name, row in business["reports"].items()
        },
        "business_records": business["records"],
        "product_apply_undo": True,
        "arbitrary_configuration_qualification": False,
    }
    (output / "acceptance.json").write_bytes(canonical_bytes(result))
    return {
        "accepted": True,
        "preview_id": preview["preview_id"],
        "operation_id": operation,
        "inventory_digests": result["inventory_digests"],
        "business_reports": {
            name: row["status"] for name, row in business["reports"].items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "owned-profile",
        "release-zip",
        "scanner",
        "platform",
        "ibcmd",
        "cfe",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("release-sha256", "platform-sha256", "ibcmd-sha256"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(verify(parser.parse_args()), ensure_ascii=False), flush=True)
