"""Real retained snapshots; fake native boundary is not platform acceptance."""
import hashlib
import json

import pytest

import rentgen_core as api
from rentgen_core.native_platform import NativePlatform
from rentgen_core.platform_check import check_proposal_platform_json
from rentgen_core.proposals import ProposalLimits, create_proposal_presentation
from rentgen_core.source_configuration import SourceLayerSpec, configure_source_layers
from project_access_test_support import force_legacy_membership
import test_project_core_publication as fixtures

project, scanner, pytestmark = fixtures.project, fixtures.scanner, fixtures.pytestmark
LIMITS = ProposalLimits(1048576, 1048576, 1572864, 262144)


@pytest.fixture
def candidate(project, tmp_path):
    ctx, resolver, module, _ = project
    (ctx.source_root / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>Test</Name></Properties></Configuration></MetaDataObject>",
        "utf-8",
    )
    configure_source_layers(
        ctx,
        (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
        expected_revision=1,
    )
    fixtures.publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    ref = selected.sources.resolve(
        "base", module.relative_to(ctx.source_root).as_posix()
    )
    raw = create_proposal_presentation(
        selected, ref, module.read_bytes().replace(b"1", b"2"), limits=LIMITS
    ).canonical_json
    executable = tmp_path / "1cv8.exe"
    executable.write_bytes(b"unit test, never executed")
    platform = NativePlatform(
        executable, hashlib.sha256(executable.read_bytes()).hexdigest()
    )
    return selected, raw, platform


def test_materializes_only_snapshot_and_pins_exact_candidate(
    candidate, project, monkeypatch
):
    ctx, raw, platform = candidate
    original = project[2].read_bytes()
    head = api.get_project_head(ctx)
    project[2].write_bytes(b"unrelated live changes")
    calls = []

    def check(self, before, after, target, run, authorize):
        authorize()
        calls.append(run)
        assert (before / target).read_bytes() == original
        assert (after / target).read_bytes() == original.replace(b"1", b"2")
        with pytest.raises(OSError):
            (after / target).write_bytes(b"tamper")
        return {
            "baseline": {"status": "passed"},
            "candidate": {"status": "diagnostics_present"},
        }

    monkeypatch.setattr(NativePlatform, "check", check)
    result = check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    assert (
        result["candidate_sha256"]
        == hashlib.sha256(original.replace(b"1", b"2")).hexdigest()
    )
    assert result["source_ref"] == json.loads(raw)["source_ref"]
    assert result["baseline_input_sha256"] != result["candidate_input_sha256"]
    assert json.loads((calls[0] / "report.json").read_text("utf-8")) == result
    assert api.get_project_head(ctx) == head
    assert project[2].read_bytes() == b"unrelated live changes"


def test_revocation_during_native_check_withholds_report(candidate, monkeypatch):
    ctx, raw, platform = candidate

    def check(self, before, after, target, run, authorize):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:admin"})
        return {"log": "must not be returned"}

    monkeypatch.setattr(NativePlatform, "check", check)
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not list((ctx.state.path.parent / "platform-checks").rglob("report.json"))


def test_mismatched_executable_prevents_materialization(candidate):
    ctx, raw, platform = candidate
    wrong = NativePlatform(platform.executable, "0" * 64)
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(ctx, raw, wrong, limits=LIMITS)
    assert error.value.code == "PLATFORM_BINARY_MISMATCH"
    assert not (ctx.state.path.parent / "platform-checks").exists()


def test_access_denied_before_bad_payload_and_executable(candidate):
    ctx, _, platform = candidate
    platform.executable.unlink()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(ctx, b"invalid", platform, limits=LIMITS)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_unknown_layer_format_is_refused_before_binary_read(project, tmp_path):
    ctx, resolver, module, _ = project
    fixtures.publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    ref = selected.sources.resolve(
        "base", module.relative_to(ctx.source_root).as_posix()
    )
    raw = create_proposal_presentation(
        selected, ref, module.read_bytes(), limits=LIMITS
    ).canonical_json
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            selected,
            raw,
            NativePlatform(tmp_path / "1cv8.exe", "0" * 64),
            limits=LIMITS,
        )
    assert error.value.code == "PLATFORM_SOURCE_UNSUPPORTED"
