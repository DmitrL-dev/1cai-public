"""Profile creation must not silently alter an existing editor or select a project."""
import importlib.util
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4
from io import BytesIO
from zipfile import ZipFile

import pytest


SPEC = importlib.util.spec_from_file_location(
    "open_editor_prepare",
    Path(__file__).resolve().parents[2] / "integrations/open-editor/prepare.py",
)
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    files = {}
    for name in ("python", "registry", "editor", "cline_vsix"):
        files[name] = tmp_path / (name + " ' $() проба")
        files[name].write_bytes(name.encode())
    project_id = str(uuid4())
    editor_cli = tmp_path / "version/resources/app/out/cli.js"
    editor_cli.parent.mkdir(parents=True)
    editor_cli.write_text("editor cli", encoding="utf-8")
    monkeypatch.setattr(profile, "CLINE_SHA256", profile.digest(files["cline_vsix"]))
    monkeypatch.setattr(
        profile, "probe", lambda *_: ({"project_id": project_id}, "0.1.0.dev7")
    )
    return {**files, "project_id": project_id, "output": tmp_path / "new profile"}


def test_ambiguous_editor_cli_is_not_guessed(inputs):
    other = inputs["editor"].parent / "other/resources/app/out/cli.js"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"other version")
    with pytest.raises(ValueError, match="Editor CLI"):
        profile.prepare(**inputs)
    assert not inputs["output"].exists()


@pytest.mark.parametrize(
    "version", ["0.1.0.dev8", "0.1.0.dev9", "0.1.0.dev10", "0.1.0.dev11", "0.1.0.dev12", "0.1.0.dev13", "0.1.0.dev14", "0.1.0.dev15", "0.1.0.dev16"]
)
def test_profile_records_actual_core_version(inputs, monkeypatch, version):
    monkeypatch.setattr(
        profile,
        "probe",
        lambda *_: ({"project_id": inputs["project_id"]}, version),
    )
    profile.prepare(**inputs)
    value = json.loads((inputs["output"] / "profile.json").read_text("utf-8"))
    assert value["core_version"] == version
    manifest = (
        Path(__file__).resolve().parents[2] / "integrations/vscode-rentgen/package.json"
    )
    assert (
        value["companion_version"] == json.loads(manifest.read_text("utf-8"))["version"]
    )


def test_existing_profile_is_never_overwritten(inputs):
    inputs["output"].mkdir()
    marker = inputs["output"] / "settings.json"
    marker.write_bytes(b"user settings")
    with pytest.raises(FileExistsError):
        profile.prepare(**inputs)
    assert marker.read_bytes() == b"user settings"
    assert list(inputs["output"].iterdir()) == [marker]


def test_unknown_or_denied_project_leaves_no_profile(inputs, monkeypatch):
    def denied(*_):
        raise ValueError("PROJECT_ACCESS_DENIED")

    monkeypatch.setattr(profile, "probe", denied)
    with pytest.raises(ValueError, match="PROJECT_ACCESS_DENIED"):
        profile.prepare(**inputs)
    assert not inputs["output"].exists()


@pytest.mark.parametrize("field", ["project_id", "cline_vsix"])
def test_invalid_identity_or_modified_release_refused(inputs, field):
    if field == "project_id":
        inputs[field] = "default"
    else:
        inputs[field].write_bytes(b"changed package")
    with pytest.raises(ValueError):
        profile.prepare(**inputs)
    assert not inputs["output"].exists()


def test_generated_launch_uses_data_not_shell_interpolation(inputs):
    profile.prepare(**inputs)
    root = inputs["output"]
    manifest = json.loads((root / "profile.json").read_text("utf-8"))
    assert manifest["editor"] == str(inputs["editor"].resolve())
    assert manifest["project_id"] == inputs["project_id"]
    assert manifest["cline_bundle"] == "legacy"
    config = json.loads(
        (
            root
            / "editor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        ).read_text("utf-8")
    )["mcpServers"]["rentgen"]
    assert config["command"] == str(inputs["python"].resolve())
    assert config["args"] == [
        "-I",
        "-m",
        "rentgen_core.stdio_mcp",
        "--registry",
        str(inputs["registry"].resolve()),
        "--project",
        inputs["project_id"],
    ] + [part for name in profile.MCP_EDITOR_TOOLS for part in ("--allow-tool", name)]
    assert manifest["mcp_tools"] == list(profile.MCP_EDITOR_TOOLS)
    assert config["autoApprove"] == []
    state = json.loads((root / "cline/data/globalState.json").read_text("utf-8"))
    assert state["telemetrySetting"] == "disabled"
    assert not any(state["autoApprovalSettings"]["actions"].values())
    assert "actModeApiProvider" not in state
    launcher = (root / "launch.ps1").read_text("utf-8")
    assert str(inputs["editor"]) not in launcher
    assert "Invoke-Expression" not in launcher
    assert "finally" in launcher
    assert "$env:CLINE_BUNDLE_OVERRIDE = 'legacy'" in launcher
    assert "$env:CLINE_BUNDLE_OVERRIDE = $priorBundle" in launcher
    assert "$env:RENTGEN_EDITOR_PROFILE = $PSScriptRoot" in launcher
    assert "$env:RENTGEN_EDITOR_PROFILE = $priorProfile" in launcher
    assert inputs["project_id"] in (root / "workspace/START-HERE.md").read_text("utf-8")


def test_companion_is_reproducible_and_profile_binds_installed_bytes(inputs):
    first = profile.companion_package()
    assert profile.companion_package() == first
    profile.prepare(**inputs)
    root = inputs["output"]
    assert (root / "assets/rentgen-companion.vsix").read_bytes() == first
    manifest = json.loads((root / "profile.json").read_text("utf-8"))
    assert manifest["companion_sha256"] == hashlib.sha256(first).hexdigest()
    with ZipFile(BytesIO(first)) as archive:
        package = json.loads(archive.read("extension/package.json"))
        assert package["version"] == manifest["companion_version"]
        assert package["license"] == "MIT"
        assert not package.get("dependencies")
        assert "extension/build.py" in archive.namelist()
        assert "extension/lib/core.cjs" in archive.namelist()
        assert "extension/LICENSE.txt" in archive.namelist()
        for name in ("run_repair.py", "repair_workflow.py", "repair_model.py"):
            assert archive.read("extension/repair/" + name) == (
                Path(profile.__file__)
                .with_name(name)
                .read_text("utf-8")
                .encode("utf-8")
            )
        unpacked = root / "unpacked"
        archive.extractall(unpacked)
    spec = importlib.util.spec_from_file_location(
        "unpacked_companion_build", unpacked / "extension/build.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.build_bytes() == first


def test_missing_companion_sources_leave_no_profile(inputs, monkeypatch):
    def missing():
        raise FileNotFoundError("companion source missing")

    monkeypatch.setattr(profile, "companion_package", missing)
    with pytest.raises(FileNotFoundError, match="companion source"):
        profile.prepare(**inputs)
    assert not inputs["output"].exists()


def test_local_model_configuration_is_explicit(inputs):
    profile.prepare(**inputs, ollama_model="qwen3.5:9b")
    state = json.loads(
        (inputs["output"] / "cline/data/globalState.json").read_text("utf-8")
    )
    assert state["actModeApiProvider"] == "ollama"
    assert state["planModeOllamaModelId"] == "qwen3.5:9b"
    assert state["ollamaBaseUrl"] == "http://127.0.0.1:11434"


def test_context_tokens_is_an_optional_last_keyword_argument():
    parameters = tuple(inspect.signature(profile.prepare).parameters.values())
    assert parameters[-1].name == "context_tokens"
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default == 32768


def test_default_context_tokens_are_recorded_in_profile_and_cline(inputs):
    profile.prepare(**inputs, ollama_model="qwen3.5:9b")
    root = inputs["output"]
    manifest = json.loads((root / "profile.json").read_text("utf-8"))
    state = json.loads((root / "cline/data/globalState.json").read_text("utf-8"))
    assert type(manifest["context_tokens"]) is int
    assert manifest["context_tokens"] == 32768
    assert state["ollamaApiOptionsCtxNum"] == "32768"


@pytest.mark.parametrize("context_tokens", [8192, 16384, 32768])
def test_explicit_context_tokens_match_cline_setting(inputs, context_tokens):
    profile.prepare(
        **inputs, ollama_model="qwen3.5:9b", context_tokens=context_tokens
    )
    root = inputs["output"]
    manifest = json.loads((root / "profile.json").read_text("utf-8"))
    state = json.loads((root / "cline/data/globalState.json").read_text("utf-8"))
    assert type(manifest["context_tokens"]) is int
    assert manifest["context_tokens"] == context_tokens
    assert state["ollamaApiOptionsCtxNum"] == str(context_tokens)


@pytest.mark.parametrize(
    "context_tokens", [True, False, None, "8192", 8192.0, 8192.5, 0, 4096, 32769]
)
def test_invalid_context_tokens_fail_before_profile_activity(
    inputs, monkeypatch, context_tokens
):
    def unexpected_activity(*_args, **_kwargs):
        raise AssertionError("Invalid context tokens reached profile activity")

    monkeypatch.setattr(profile, "probe", unexpected_activity)
    monkeypatch.setattr(profile, "companion_package", unexpected_activity)
    with pytest.raises(ValueError):
        profile.prepare(**inputs, context_tokens=context_tokens)
    assert not inputs["output"].exists()


@pytest.mark.parametrize("context_tokens", [8192, 16384, 32768])
def test_cli_accepts_context_tokens_as_an_integer(monkeypatch, context_tokens):
    captured = {}

    def capture_prepare(**kwargs):
        captured.update(kwargs)
        return {"profile": "prepared"}

    monkeypatch.setattr(profile, "prepare", capture_prepare)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare.py",
            "--python", "python.exe",
            "--registry", "registry.sqlite3",
            "--editor", "editor.exe",
            "--cline-vsix", "cline.vsix",
            "--output", "new-profile",
            "--project-id", str(uuid4()),
            "--context-tokens", str(context_tokens),
        ],
    )
    profile.main()
    assert type(captured["context_tokens"]) is int
    assert captured["context_tokens"] == context_tokens


def test_explicit_diagnostics_root_is_confined_to_mcp_startup(inputs):
    root = inputs["output"].parent / "Диагностика"
    root.mkdir()
    profile.prepare(**inputs, diagnostics_local_app_data=root)
    manifest = json.loads((inputs["output"] / "profile.json").read_text("utf-8"))
    assert manifest["diagnostics_local_app_data"] == str(root.resolve())
    settings = (
        inputs["output"]
        / "editor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    )
    server = json.loads(settings.read_text("utf-8"))["mcpServers"]["rentgen"]
    assert server["env"]["LOCALAPPDATA"] == str(root.resolve())
    assert "LOCALAPPDATA" not in (inputs["output"] / "launch.ps1").read_text("utf-8")


def test_missing_diagnostics_root_leaves_no_profile(inputs):
    with pytest.raises(FileNotFoundError):
        profile.prepare(
            **inputs, diagnostics_local_app_data=inputs["output"] / "absent"
        )
    assert not inputs["output"].exists()


@pytest.mark.parametrize(
    "change", [{"installed": False}, {"mcp": "0.0"}, {"python": [3, 12]}]
)
def test_probe_rejects_unsupported_or_checkout_runtime(monkeypatch, change):
    runtime = {
        "core": "0.1.0.dev7",
        "mcp": "1.30.0",
        "platform": "win32",
        "python": [3, 11],
        "installed": True,
        **change,
    }
    monkeypatch.setattr(
        profile.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout=json.dumps(runtime)),
    )
    with pytest.raises(ValueError, match="installed core"):
        profile.probe(Path("python.exe"), Path("registry"), str(uuid4()))


def test_scanner_remains_trusted_startup_argument(inputs):
    scanner = inputs["editor"].parent / "bsl-scan.exe"
    scanner.write_bytes(b"test scanner")
    profile.prepare(**inputs, scanner=scanner)
    config = json.loads(
        (
            inputs["output"]
            / "editor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        ).read_text("utf-8")
    )
    assert config["mcpServers"]["rentgen"]["args"][-2:] == ["--scanner", str(scanner)]
