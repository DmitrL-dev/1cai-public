"""Prove installed Core dev10 live metadata apply against an owned 1C fixture."""

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import shutil
import time
from uuid import uuid4
import zipfile

import rentgen_core as api
from rentgen_core import (
    metadata_apply,
    metadata_live_apply,
    metadata_plans,
    metadata_runs,
)
from rentgen_core.edt_execution import write_record
from rentgen_core.edt_inventory import exported_inventory
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.metadata_preview import build_preview
from rentgen_core.native_platform import CONTEXTS, NativePlatform
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_graph.snapshot_adapter import (
    RentgenCapturedGoBuilder,
    RentgenGraphReaderFactory,
)

from verify_edt_metadata_fixture import verify_structure
import verify_metadata_migration as migration


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "packaging/fixtures/edt-metadata-v1"
if not __debug__:
    raise RuntimeError("Verification requires assertions; do not use Python -O")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_release(archive, expected_hash, scanner):
    require(digest(archive) == expected_hash, "Public release ZIP SHA256 mismatch")
    require(
        importlib.metadata.version("rentgen-core") == "0.1.0.dev10", "Not Core dev10"
    )
    package_root = Path(api.__file__).resolve().parent.parent
    require(not package_root.is_relative_to(ROOT), "Core imported from source checkout")
    with zipfile.ZipFile(archive) as bundle:
        wheel_name = next(
            name
            for name in bundle.namelist()
            if name.endswith("/rentgen_core-0.1.0.dev10-py3-none-any.whl")
        )
        with zipfile.ZipFile(io.BytesIO(bundle.read(wheel_name))) as wheel:
            names = [
                name
                for name in wheel.namelist()
                if name.startswith(("rentgen_core/", "rentgen_graph/"))
                and not name.endswith("/")
            ]
            require(bool(names), "Core wheel contains no package files")
            for name in names:
                require(
                    (package_root / name).read_bytes() == wheel.read(name),
                    "Installed Core differs from public wheel: " + name,
                )
        bundled_scanner = next(
            name for name in bundle.namelist() if name.endswith("/bsl-scan.exe")
        )
        require(
            scanner.read_bytes() == bundle.read(bundled_scanner),
            "Scanner differs from release",
        )
        return {
            "archive_sha256": expected_hash,
            "wheel_sha256": sha256(bundle.read(wheel_name)),
            "scanner_sha256": digest(scanner),
            "installed_files_checked": len(names),
        }


def prepare_preview(root, scanner):
    source = root / "source"
    shutil.copytree(FIXTURE / "created", source)
    original = exported_inventory(source, authorize=lambda: None)
    manifest = json.loads((FIXTURE / "manifest.json").read_text("utf-8"))["files"]
    expected = {
        name.removeprefix("created/"): value
        for name, value in manifest.items()
        if name.startswith("created/")
    }
    require(
        {row["path"]: row["sha256"] for row in original} == expected,
        "Owned source differs from accepted fixture",
    )

    owner = api.Principal("native-proof-owner", "local_os")
    registry = api.ProjectRegistry.create(root / "registry.sqlite3")
    registered = registry.register(
        owner,
        source_root=source,
        state_root=root / "state",
        display_name="Owned metadata native proof",
    )
    resolver = api.ContextResolver(
        registry, graph_reader_factory=RentgenGraphReaderFactory()
    )
    ctx = resolver.resolve_context(owner, api.Explicit(registered.project_id))
    api.configure_source_layers(
        ctx,
        (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
        expected_revision=1,
    )
    api.capture_and_publish(
        ctx,
        expected_head=api.get_project_head(ctx),
        builder=RentgenCapturedGoBuilder(scanner),
        operation_id=str(uuid4()),
    )
    ctx = resolver.resolve_context(owner, api.Explicit(registered.project_id))
    request = {
        "schema": 1,
        "operation": "rename_catalog_attribute",
        "snapshot": asdict(ctx.snapshot),
        "layer_id": "base",
        "catalog": {"name": "Products", "uuid": "fb28b18e-d2a3-4f48-8390-c0d609c9e7c0"},
        "attribute": {
            "name": "Article",
            "uuid": "eb298009-8fc5-4a2f-8812-902daeed99df",
        },
        "new_name": "SKU",
    }
    plan = metadata_plans.create_plan(ctx, request)
    preview_operation = str(uuid4())
    run = metadata_runs.run_path(ctx, preview_operation)
    run.mkdir(parents=True)
    binding = {
        "schema": 1,
        "project_id": ctx.project_id,
        "operation_id": preview_operation,
        "profile_id": "a" * 64,
        "plan": plan,
    }
    write_record(run / "runtime-request.json", binding)
    metadata_plans.materialize(ctx, plan, run / "input")
    shutil.copytree(FIXTURE / "created", run / "baseline-xml")
    shutil.copytree(FIXTURE / "renamed", run / "candidate-xml")
    preview = metadata_runs._result(binding, build_preview(ctx, plan, run))
    write_record(run / "preview.json", preview)
    write_record(
        run / "runtime-closed.json", {"status": "closed", "metadata_verified": False}
    )
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
        and preflight["reasons"]
        == ["live_apply_not_implemented", "normalization_not_qualified"],
        "Read-only preflight contract changed",
    )
    return ctx, run, preview, operation, original, preflight


def check_native_source(source, folder, executable, expected_hash):
    folder.mkdir()
    base = folder / "infobase"
    restored = folder / "roundtrip"
    restored.mkdir()
    native = NativePlatform(executable, expected_hash)
    deadline = time.monotonic() + 600
    steps = []

    def authorize():
        require(digest(executable) == expected_hash, "1C executable changed")

    for name, arguments in (
        ("create", ["CREATEINFOBASE", f'File="{base}";Locale=ru_RU;']),
        ("load-live-source", ["DESIGNER", "/F", base, "/LoadConfigFromFiles", source]),
        ("update", ["DESIGNER", "/F", base, "/UpdateDBCfg"]),
        ("check", ["DESIGNER", "/F", base, "/CheckConfig", *CONTEXTS]),
        ("dump", ["DESIGNER", "/F", base, "/DumpConfigToFiles", restored]),
    ):
        step = native.invoke(folder, name, arguments, authorize, deadline)
        steps.append(step)
        (folder / "steps.json").write_bytes(canonical_bytes(steps))
        require(step["exit_code"] == 0, "Native step failed: " + name)
        print(json.dumps({"native_step": name, "exit_code": 0}), flush=True)
    structure = verify_structure(source, restored, "renamed")
    return {
        "steps": [
            {"name": name, "exit_code": row["exit_code"]}
            for name, row in zip(
                ("create", "load-live-source", "update", "check", "dump"), steps
            )
        ],
        "structure": structure,
    }


def verify(args):
    release = check_release(
        args.release_zip.resolve(strict=True),
        args.release_sha256,
        args.scanner.resolve(strict=True),
    )
    platform = args.platform.resolve(strict=True)
    ibcmd = args.ibcmd.resolve(strict=True)
    cfe = args.cfe.resolve(strict=True)
    require(digest(platform) == args.platform_sha256, "1C platform SHA256 mismatch")
    require(digest(ibcmd) == args.ibcmd_sha256, "ibcmd SHA256 mismatch")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    ctx, run, preview, operation, before, preflight = prepare_preview(
        root, args.scanner
    )
    candidate = preview["preview"]["inventories"]["candidate"]
    applied = metadata_live_apply.apply_live(ctx, operation)
    try:
        after = exported_inventory(ctx.source_root, authorize=lambda: None)
        require(
            after == candidate, "Live source differs from retained candidate inventory"
        )
        native = check_native_source(
            ctx.source_root, root / "native", platform, args.platform_sha256
        )
    finally:
        undone = metadata_live_apply.undo_live(ctx, operation)
    restored = exported_inventory(ctx.source_root, authorize=lambda: None)
    require(restored == before, "CAS undo did not restore original inventory")
    (root / "live-native.json").write_bytes(
        canonical_bytes(
            {
                "preview_id": preview["preview_id"],
                "operation_id": operation,
                "preflight_status": preflight["status"],
                "apply_status": applied["status"],
                "undo_status": undone["status"],
                "native": native,
                "inventory_digests": {
                    "original": sha256(canonical_bytes(before)),
                    "applied": sha256(canonical_bytes(after)),
                    "restored": sha256(canonical_bytes(restored)),
                },
            }
        )
    )
    local_data = root / "RentgenMigrationData.bsl"
    shutil.copyfile(migration.DATA, local_data)
    migration.DATA = local_data
    business = migration.verify(
        argparse.Namespace(
            input_run=run,
            output=root / "business",
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
        "YAxUnit source inventories differ from retained preview",
    )
    result = {
        "schema": 1,
        "source": "installed public Core dev10 on owned synthetic Designer XML fixture",
        "release": release,
        "platform_sha256": args.platform_sha256,
        "ibcmd_sha256": args.ibcmd_sha256,
        "engine_cfe_sha256": digest(cfe),
        "preview_id": preview["preview_id"],
        "operation_id": operation,
        "preflight_status": preflight["status"],
        "apply_status": applied["status"],
        "live_source_written": applied["live_source_written"],
        "changed_paths": applied["changed_paths"],
        "native": native,
        "undo_status": undone["status"],
        "inventory_digests": {
            "original": sha256(canonical_bytes(before)),
            "applied": sha256(canonical_bytes(after)),
            "restored": sha256(canonical_bytes(restored)),
        },
        "business_reports": {
            name: report["status"] for name, report in business["reports"].items()
        },
        "business_records": business["records"],
        "product_apply_undo": True,
        "arbitrary_configuration_qualification": False,
    }
    (root / "acceptance.json").write_bytes(canonical_bytes(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("release-zip", "scanner", "platform", "ibcmd", "cfe", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("release-sha256", "platform-sha256", "ibcmd-sha256"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(verify(parser.parse_args()), ensure_ascii=False), flush=True)
