"""Installed verification gates must follow the candidate's exact kit version."""
from pathlib import Path
import re
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_every_installed_core_verifier_uses_current_candidate_scanner():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    version = project["project"]["version"]
    workflow = yaml.safe_load((ROOT / ".github/workflows/core-ci.yml").read_text("utf-8"))
    steps = workflow["jobs"]["windows"]["steps"]
    by_name = {step["name"]: step for step in steps if "name" in step}
    expected = "output/core-kit/rentgen-core-" + version + "-windows-py311/bsl-scan.exe"
    gates = {
        "Verify installed cross-client draft editing": "scripts/verification/draft_companion/verify.py",
        "Verify installed snapshot comparison": "scripts/verification/verify_snapshot_diff_delivery.py",
        "Verify installed observer across processes": "scripts/verification/verify_observer_delivery.py",
    }
    for name, script in gates.items():
        command = by_name[name]["run"]
        assert script in command
        assert re.findall(r"--scanner\s+(\S+)", command) == [expected]
        assert "--python output/core-kit/offline-install/environment/Scripts/python.exe" in command
    draft = by_name["Verify installed cross-client draft editing"]
    assert draft["timeout-minutes"] == 4
    assert draft["env"]["CI_CHECKOUT_SHA"] == "${{ github.sha }}"
    assert draft["env"]["CI_TRIGGER_HEAD"] == "${{ github.event.pull_request.head.sha || github.sha }}"
    assert "--expected-checkout $env:CI_CHECKOUT_SHA --trigger-head $env:CI_TRIGGER_HEAD" in draft["run"]
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in draft["run"]
    evidence = by_name["Upload cross-client draft evidence"]
    assert evidence["if"] == "always()"
    assert evidence["with"]["path"].splitlines() == [
        "output/draft-companion-evidence/" + name
        for name in ("acceptance.json", "source-binding.json", "scenario.json", "node.log")
    ]
    archives = [line.strip() for step in steps for line in step.get("with", {}).get("path", "").splitlines()
                if line.endswith("-windows-py311.zip")]
    assert archives == ["output/core-kit/rentgen-core-" + version + "-windows-py311.zip"]
