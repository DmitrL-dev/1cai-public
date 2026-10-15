"""A version bump must reach the installed checks and uploaded release inputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def windows_steps():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/core-ci.yml").read_text("utf-8")
    )
    return workflow["jobs"]["windows"]["steps"]


def resolve(tmp_path, core, companion):
    shell = shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell is required to execute the Windows workflow step")
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{core}"\n', encoding="utf-8"
    )
    package = tmp_path / "integrations/vscode-rentgen/package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"version": companion}), encoding="utf-8")
    env_file = tmp_path / "github-env"
    step = next(
        step for step in windows_steps()
        if step.get("name") == "Resolve development artifact names"
    )
    # Execute the actual step, using this test's Python even outside Actions.
    python = sys.executable.replace("'", "''")
    result = subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
         f"function python {{ & '{python}' @args }}\n" + step["run"]],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_ENV": str(env_file)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result, env_file


@pytest.mark.parametrize(
    "core,companion", [("0.1.0.dev18", "0.1.19"), ("9.12.3.dev42", "2.3.40")]
)
def test_future_versions_resolve_from_current_package_metadata(tmp_path, core, companion):
    result, env_file = resolve(tmp_path, core, companion)
    assert result.returncode == 0, result.stdout + result.stderr
    assert env_file.read_text("utf-8-sig").splitlines() == [
        f"CORE_KIT_NAME=rentgen-core-{core}-windows-py311",
        f"COMPANION_DEVELOPMENT_ASSET=rentgen-companion-{companion}-development.vsix",
    ]


@pytest.mark.parametrize(
    "core,companion", [("0.1.0", "0.1.19"), ("0.1.0.dev18", "../other")]
)
def test_invalid_versions_cannot_select_artifact_paths(tmp_path, core, companion):
    result, env_file = resolve(tmp_path, core, companion)
    assert result.returncode != 0
    assert not env_file.exists()


def test_installed_checks_and_upload_use_the_resolved_assets():
    steps = windows_steps()
    by_name = {step.get("name"): step for step in steps}
    for name in (
        "Verify installed cross-client draft editing",
        "Verify installed snapshot comparison",
        "Verify installed observer across processes",
    ):
        assert '--scanner "output/core-kit/$env:CORE_KIT_NAME/bsl-scan.exe"' in by_name[name]["run"]
    assert '"output/$env:COMPANION_DEVELOPMENT_ASSET"' in by_name["Build development companion"]["run"]
    upload = next(
        step for step in steps
        if step.get("with", {}).get("name") == "verified-core-development"
    )
    paths = upload["with"]["path"].splitlines()
    assert "output/core-kit/${{ env.CORE_KIT_NAME }}.zip" in paths
    assert "output/${{ env.COMPANION_DEVELOPMENT_ASSET }}" in paths
