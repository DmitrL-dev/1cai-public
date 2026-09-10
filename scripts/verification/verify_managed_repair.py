"""Independent CLI/BSL acceptance of the artificial exception-propagation fixture."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_editor_diagnostic import repair_variant


def verify(profile, run):
    if not __debug__:
        raise RuntimeError("Do not use Python -O for verification")
    config = json.loads((profile / "profile.json").read_text("utf-8"))
    scenario = json.loads((profile / "diagnostic-scenario.json").read_text("utf-8"))
    result = json.loads((run / "result.json").read_text("utf-8"))
    events = [
        json.loads(line)
        for line in (run / "events.jsonl").read_text("utf-8").splitlines()
    ]
    assert sum(e["phase"] == "model_requested" for e in events) == 1
    receipt = result.get("receipt") or next(
        e["receipt"] for e in events if e["phase"] == "draft_created"
    )
    assert receipt["project_id"] == config["project_id"] == scenario["project_id"]

    def cli(command, *extra):
        reply = subprocess.run(
            [
                config["python"],
                "-I",
                "-m",
                "rentgen_core",
                command,
                "--registry",
                config["registry"],
                "--project",
                config["project_id"],
                *map(str, extra),
            ],
            capture_output=True,
            timeout=90,
            env=dict(
                os.environ,
                LOCALAPPDATA=config["diagnostics_local_app_data"],
                PYTHONUTF8="1",
            ),
        )
        assert reply.returncode == 0, reply.stdout.decode("utf-8")
        return json.loads(reply.stdout)["result"]

    first = cli("draft-get", "--draft-id", receipt["draft_id"], "--revision", 1)
    second = cli("draft-get", "--draft-id", receipt["draft_id"])
    assert second["receipt"] == receipt
    original = base64.b64decode(scenario["original"], validate=True)
    raw = base64.b64decode(second["proposal"]["replacement"]["base64"], validate=True)
    assert (
        base64.b64decode(first["proposal"]["replacement"]["base64"], validate=True)
        == original
    )
    assert Path(scenario["source"]).read_bytes() == original
    assert cli("project-head") == config["head_at_setup"]
    if result["status"] == "failed":
        assert not any(e["phase"] == "edit_requested" for e in events)
        assert receipt["revision"] == 1 and raw == original
        assert (
            cli("draft-receipt", "--operation-id", receipt["operation_id"]) == receipt
        )
        return {
            "accepted": False,
            "failure": result["error"],
            "semantic_variant": None,
            "source_unchanged": True,
            "head_unchanged": True,
            "receipt": receipt,
            "model_requests": 1,
            "model": next(
                (e["metrics"] for e in events if e["phase"] == "model_failed"), {}
            ),
            "new_revision_created": False,
            "editor_ui_tested": False,
            "platform_1c_tested": False,
        }
    assert receipt["revision"] == 2
    assert sum(e["phase"] == "edit_requested" for e in events) == 1
    for saved, phase, evidence in [
        (first, "start_requested", result["before"]),
        (second, "edit_requested", result["after"]),
    ]:
        saved_receipt = saved["receipt"]
        assert (
            cli("draft-receipt", "--operation-id", saved_receipt["operation_id"])
            == saved_receipt
        )
        intent = next(e for e in events if e["phase"] == phase)
        assert intent["operation_id"] == saved_receipt["operation_id"]
        assert saved_receipt["source_ref"]["snapshot"] == scenario["snapshot"]
        assert evidence["receipt"] == saved_receipt
        diagnostic = evidence["diagnostic"]
        analysis = diagnostic["analysis"]
        assert diagnostic["proposal_content_id"] == saved["proposal"]["content_id"]
        assert diagnostic["source_ref"] == saved_receipt["source_ref"]
        assert (
            analysis["candidate_sha256"]
            == saved["proposal"]["replacement"]["raw_sha256"]
        )
        assert analysis["status"] == "completed" and analysis["exit_code"] == 0
        assert (
            analysis["runtime_verified"] is True
            and analysis["diagnostics_complete"] is True
        )
        assert analysis["coverage"] == "exact_one"
        assert evidence["tests"] == {"status": "not_run"} and evidence["apply"] == {
            "status": "unavailable"
        }
    assert any(
        d["code"] == "MissingCodeTryCatchEx"
        for d in result["before"]["diagnostic"]["analysis"]["diagnostics"]
    )
    try:
        variant = repair_variant(raw)
    except ValueError:
        variant = None
    independent = None
    clean = result["after"]["diagnostic"]["analysis"]["diagnostics"] == []
    if variant and clean:
        proposal = run / "independent-proposal.json"
        with proposal.open("x", encoding="utf-8") as stream:
            json.dump(second["proposal"], stream)
        independent = cli(
            "proposal-check",
            "--snapshot",
            scenario["snapshot"]["snapshot_id"],
            "--proposal-json",
            proposal,
            "--diagnostics-profile",
            "bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1",
        )
        analysis = independent["diagnostic"]["analysis"]
        assert analysis["status"] == "completed" and analysis["exit_code"] == 0
        assert (
            analysis["runtime_verified"] is True
            and analysis["diagnostics_complete"] is True
        )
        assert analysis["coverage"] == "exact_one" and analysis["diagnostics"] == []
        assert analysis["candidate_sha256"] == hashlib.sha256(raw).hexdigest()
    return {
        "accepted": bool(variant and clean and independent),
        "semantic_variant": variant,
        "source_unchanged": True,
        "head_unchanged": True,
        "receipt": receipt,
        "model": result["model"],
        "before": result["before"],
        "after": result["after"],
        "independent": independent,
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "model_requests": 1,
        "editor_ui_tested": False,
        "platform_1c_tested": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["profile", "run", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.profile, args.run)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "semantic_variant": report["semantic_variant"],
                "model": report["model"],
            }
        )
    )
    raise SystemExit(0 if report["accepted"] else 1)
