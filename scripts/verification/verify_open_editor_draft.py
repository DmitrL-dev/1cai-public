"""Verify the synthetic BeforeEditor -> AfterEditor task independently of the model.

Input is a trusted local acceptance profile with scenario.json and host evidence.
This checks one concrete editor workflow, not arbitrary externally supplied reports.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


ORIGINAL = b"\xef\xbb\xbfProcedure BeforeEditor() Export\r\nEndProcedure\r\n"
REPLACEMENT = ORIGINAL.replace(b"BeforeEditor", b"AfterEditor")


def verify(profile, source):
    if not __debug__:
        raise RuntimeError("Acceptance verification requires Python without -O")
    config = json.loads((profile / "profile.json").read_text("utf-8"))
    ids = json.loads((profile / "scenario.json").read_text("utf-8"))
    host = json.loads((profile / "host-acceptance.json").read_text("utf-8"))
    task = (
        profile
        / "editor/User/globalStorage/saoudrizwan.claude-dev/tasks"
        / host["task_id"]
    )
    messages_file = task / "ui_messages.json"
    messages = json.loads(messages_file.read_text("utf-8"))
    calls = [
        json.loads(m["text"]) for m in messages if m.get("say") == "use_mcp_server"
    ]
    responses = [
        json.loads(m["text"]) for m in messages if m.get("say") == "mcp_server_response"
    ]

    def cli(command, *arguments):
        result = subprocess.run(
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
                *map(str, arguments),
            ],
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, result.stdout
        return json.loads(result.stdout)["result"]

    draft = cli("draft-get", "--draft-id", ids["draft_id"])
    report = {
        "accepted": False,
        "host": host,
        "model_requests": sum(m.get("say") == "api_req_started" for m in messages),
        "duration_seconds": round((messages[-1]["ts"] - messages[0]["ts"]) / 1000, 1),
        "calls": [c["toolName"] for c in calls],
        "confirmed_revision": draft["receipt"]["revision"],
        "source_unchanged": source.read_bytes() == ORIGINAL,
        "messages_sha256": hashlib.sha256(messages_file.read_bytes()).hexdigest(),
    }
    if host["phase"] != "model-completed":
        report["failure"] = host["phase"]
        return report
    assert host["project_id"] == config["project_id"]
    assert all(
        m.get("modelInfo", {}).get("providerId", "ollama") == "ollama" for m in messages
    )
    assert all(c["serverName"] == "rentgen" for c in calls)
    names = report["calls"]
    required = [
        "rentgen_project_head",
        "rentgen_source_list",
        "rentgen_draft_start",
        "rentgen_draft_edit",
    ]
    assert [n for n in names if n != "rentgen_draft_read"] == required
    assert len(calls) == len(responses) and all(
        "result" in r and "error" not in r for r in responses
    )
    assert report["source_unchanged"] and report["confirmed_revision"] == 2
    assert cli("project-head") == config["head_at_setup"]
    assert (
        base64.b64decode(draft["proposal"]["replacement"]["base64"], validate=True)
        == REPLACEMENT
    )
    before = cli("draft-get", "--draft-id", ids["draft_id"], "--revision", "1")
    assert (
        base64.b64decode(before["proposal"]["replacement"]["base64"], validate=True)
        == ORIGINAL
    )
    for saved, operation in [(before, ids["start_id"]), (draft, ids["edit_id"])]:
        assert cli("draft-receipt", "--operation-id", operation) == saved["receipt"]
        assert any(r["result"].get("draft") == saved["receipt"] for r in responses)
    report.update(
        {
            "accepted": True,
            "candidate_sha256": hashlib.sha256(REPLACEMENT).hexdigest(),
            "revisions_verified": [1, 2],
            "head_unchanged": True,
            "receipts_matched_via_independent_cli": True,
            "model": next(
                m["modelInfo"]["modelId"] for m in messages if m.get("modelInfo")
            ),
        }
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.profile.resolve(strict=True), args.source.resolve(strict=True))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ["accepted", "confirmed_revision", "duration_seconds"]
            }
        )
    )
    raise SystemExit(0 if report["accepted"] else 1)


if __name__ == "__main__":
    main()
