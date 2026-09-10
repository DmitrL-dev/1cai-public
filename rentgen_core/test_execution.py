"""Execute a registered profile against an explicitly retained proposal."""
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from ._windows_source_tree import pinned_directory, pinned_retained
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .native_platform import NativePlatform
from .platform_check import _materialize, _pin_inputs, _run_attempt
from .platform_runs import get_platform_run, replay_run, run_path, write_record
from .proposals import parse_proposal
from .test_profiles import (
    PERMISSIONS,
    authorized,
    authorize_run,
    get_profile,
    profile_path,
)
from .yaxunit_runner import run_yaxunit


def check_proposal_tests(ctx, raw_json, profile_id, operation_id, *, limits):
    with authorized(ctx):
        proposal = parse_proposal(
            ctx, raw_json, limits=limits, authorize=lambda: _permissions(ctx)
        )
        folder = run_path(ctx, operation_id, namespace="test-runs")
        minimal = {
            "source_ref": asdict(proposal.source_ref),
            "proposal_content_id": proposal.content_id,
            "profile_id": profile_id,
        }
        if folder.exists():
            saved = get_platform_run(ctx, operation_id, namespace="test-runs")
            binding = saved["request"]["input"] if saved["request"] else {}
            if any(binding.get(k) != v for k, v in minimal.items()):
                raise CoreError(
                    "PLATFORM_RUN_CONFLICT",
                    "Test operation belongs to different inputs",
                )
            return replay_run(ctx, operation_id, binding, namespace="test-runs")
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(PERMISSIONS)
            layers = tx.get_snapshot_layers(ctx.snapshot.snapshot_id)
        if (
            not proposal.source_ref.relative_path.lower().endswith(".bsl")
            or len(layers) != 1
            or layers[0].kind != "base"
            or layers[0].source_format != "designer_xml"
            or layers[0].layer_id != proposal.source_ref.layer_id
        ):
            raise CoreError(
                "PLATFORM_SOURCE_UNSUPPORTED",
                "Tests require one retained Designer XML base",
            )
        profile_folder = profile_path(ctx, profile_id)
        with ExitStack() as inputs:
            inputs.enter_context(
                pinned_retained(profile_folder / "profile.json", 1024 * 1024)
            )
            profile = get_profile(ctx, profile_id, active=True)["definition"]
            for name in ("platform", "ibcmd"):
                raw = inputs.enter_context(
                    pinned_retained(Path(profile[name]["path"]), 64 * 1024**2)
                )
                if sha256(raw) != profile[name]["sha256"]:
                    raise CoreError(
                        "PLATFORM_BINARY_MISMATCH", "Registered executable changed"
                    )
            engine = profile_folder / "engine.cfe"
            raw = inputs.enter_context(pinned_retained(engine, 8 * 1024**2))
            if sha256(raw) != profile["engine_sha256"]:
                raise CoreError("TEST_ENGINE_INVALID", "Registered engine changed")
            platform = NativePlatform(
                Path(profile["platform"]["path"]), profile["platform"]["sha256"]
            )
            binding = {
                **minimal,
                "platform_executable_sha256": platform.executable_sha256,
            }
            parent = folder.parent
            if any(c in str(parent) for c in (";", '"', "\r", "\n")):
                raise CoreError(
                    "PLATFORM_WORKSPACE_INVALID", "Unsupported test workspace path"
                )
            parent.mkdir(exist_ok=True)
            with pinned_directory(parent):
                try:
                    folder.mkdir()
                except FileExistsError:
                    return replay_run(ctx, operation_id, binding, namespace="test-runs")
                with _run_attempt(ctx, folder, binding) as resources:
                    platform = NativePlatform(
                        platform.executable, platform.executable_sha256, resources.job
                    )

                    def check():
                        authorize_run(ctx, profile_id)
                        resources.check()

                    before, after = folder / "baseline", folder / "candidate"
                    before.mkdir()
                    after.mkdir()
                    inventories = _materialize(ctx, proposal, before, after)
                    with _pin_inputs(before, inventories[0]), _pin_inputs(
                        after, inventories[1]
                    ):
                        tests = run_yaxunit(
                            platform,
                            Path(profile["ibcmd"]["path"]),
                            engine,
                            profile["modules"],
                            before,
                            after,
                            proposal.source_ref.relative_path,
                            folder,
                            check,
                        )
                    resources.finished()
                    check()
                    from .native_scratch import clear_ibcmd_scratch

                    cleanup = clear_ibcmd_scratch(folder)
                    resources.finished()
                    check()
                    report = {
                        "schema": 1,
                        "run_id": operation_id,
                        **binding,
                        "candidate_sha256": sha256(proposal.replacement_bytes),
                        "baseline_input_sha256": sha256(
                            canonical_bytes(inventories[0])
                        ),
                        "candidate_input_sha256": sha256(
                            canonical_bytes(inventories[1])
                        ),
                        "tests": tests,
                        "scratch_cleanup": cleanup,
                        "apply": {"status": "unavailable"},
                        "evidence": "local_unattested",
                        "runtime_dependencies": "not_fully_pinned",
                    }
                    report["report_sha256"] = sha256(canonical_bytes(report))
                    write_record(ctx, folder, "report", report)
                    return report


def _permissions(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)
