"""Constructed retained YAxUnit run bytes in the exact runner layout.

These bytes are explicit test inputs. They never stand in for a native 1C run.
"""
from base64 import b64decode, b64encode
import os
from pathlib import PurePosixPath, PureWindowsPath
from uuid import uuid4

from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.test_profiles import ENGINE_SHA256
from rentgen_core.test_run_qualification import phase_steps

ENGINE = {
    "Configuration.xml": b"<Configuration>engine</Configuration>",
    "CommonModules/\u042e\u0422\u0422\u0435\u0441\u0442\u044b.xml": b"<CommonModule/>",
}
TARGET = "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"


def modules(*specs):
    rows = []
    for name, tests in specs or (("RentgenTests", ("One", "Two")),):
        raw = ("\ufeff// " + name + "\r\n").encode("utf-8")
        rows.append(
            {
                "name": name,
                "base64": b64encode(raw).decode(),
                "sha256": sha256(raw),
                "tests": list(tests),
            }
        )
    return rows


def profile_record(project_id, module_rows, *, engine_sha256, platform_sha256):
    # Profile validation requires absolute paths on the evaluating OS.
    base = "C:\\fixture\\" if os.name == "nt" else "/fixture/"
    definition = {
        "schema": 1,
        "name": "Constructed profile",
        "platform": {"path": base + "1cv8.exe", "sha256": platform_sha256},
        "ibcmd": {"path": base + "ibcmd.exe", "sha256": platform_sha256},
        "engine_sha256": engine_sha256,
        "modules": module_rows,
    }
    return {
        "profile_id": sha256(canonical_bytes(definition)),
        "project_id": project_id,
        "definition": definition,
        "registered_by": {"id": "fixture", "authority": "local_os"},
        "registered_at": "2026-10-16T00:00:00+00:00",
        "enabled": True,
    }


def _junit(module_rows, outcome):
    cases, counts = [], {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for module in module_rows:
        for test in module["tests"]:
            child = ""
            if not cases and outcome == "failed":
                child, counts["failures"] = '<failure message="constructed"/>', 1
            if not cases and outcome == "incomplete":
                child, counts["skipped"] = '<skipped message="constructed"/>', 1
            counts["tests"] += 1
            cases.append(
                f'<testcase classname="{module["name"]}.{test}" name="{test}" '
                f'context="\u0421\u0435\u0440\u0432\u0435\u0440">{child}</testcase>'
            )
    attrs = " ".join(f'{key}="{value}"' for key, value in counts.items())
    xml = f"<testsuites><testsuite {attrs}>{''.join(cases)}</testsuite></testsuites>"
    return xml.encode("utf-8"), b"1" if outcome == "failed" else b"0"


def _parsed(module_rows, junit, exit_raw, outcome):
    cases = []
    for module in module_rows:
        for test in module["tests"]:
            first = not cases
            cases.append(
                {
                    "classname": module["name"] + "." + test,
                    "name": test,
                    "context": "\u0421\u0435\u0440\u0432\u0435\u0440",
                    "outcome": (
                        "failure"
                        if first and outcome == "failed"
                        else "skipped"
                        if first and outcome == "incomplete"
                        else "passed"
                    ),
                }
            )
    failures = int(outcome == "failed")
    skipped = int(outcome == "incomplete")
    return {
        "status": outcome,
        "counts": {
            "tests": len(cases),
            "failures": failures,
            "errors": 0,
            "skipped": skipped,
            "passed": len(cases) - failures - skipped,
        },
        "cases": cases,
        "junit_sha256": sha256(junit),
        "exit_file_sha256": sha256(exit_raw),
        "framework_exit_code": int(exit_raw),
        "evidence": "parsed_unattested",
    }


def runner_outputs(
    run_root, module_rows, *, target, baseline, candidate, outcomes=("failed", "passed")
):
    """Return (tests, files) exactly as rentgen_core.yaxunit_runner writes them."""
    root = PureWindowsPath(run_root)
    files, steps, results = {}, [], {}
    engine_files = dict(ENGINE)
    for module in module_rows:
        engine_files["CommonModules/" + module["name"] + ".xml"] = b"<CommonModule/>"
        engine_files["CommonModules/" + module["name"] + "/Ext/Module.bsl"] = (
            b64decode(module["base64"])
        )
    executed_before = False
    for phase, source, outcome in zip(
        ("baseline", "candidate"), (baseline, candidate), outcomes
    ):
        executed = outcome != "not_run"
        files[phase + "-roundtrip/" + target] = source
        for name in phase_steps(
            phase, executed=executed, engine_dump=executed and not executed_before
        ):
            if name.endswith("-extension-properties"):
                step = {"name": name, "exit_code": 0}
                for stream in ("stdout", "stderr"):
                    raw = f"constructed ibcmd {name} {stream}".encode()
                    files[name + "." + stream] = raw
                    step[stream + "_sha256"] = sha256(raw)
            else:
                log = f"\u0428\u0430\u0433 {name}\r\n".encode("utf-8")
                step = {
                    "name": name,
                    "exit_code": 101 if name.endswith("-compile") and not executed else 0,
                    "log": log.decode("utf-8-sig"),
                    "log_sha256": sha256(log),
                    "elapsed_ms": 7,
                }
                files[name + ".log"] = log
                for stream in ("stdout", "stderr"):
                    raw = f"constructed {name} {stream}".encode()
                    files[name + "." + stream] = raw
                    step[stream + "_sha256"] = sha256(raw)
            steps.append(step)
        if not executed:
            results[phase] = {
                "status": "not_run",
                "reason": "compiler_diagnostics",
                "native_module_sha256": sha256(source),
            }
            continue
        executed_before = True
        junit, exit_raw = _junit(module_rows, outcome)
        settings = canonical_bytes(
            {
                "filter": {"modules": [m["name"] for m in module_rows]},
                "reportFormat": "jUnit",
                "reportPath": str(root / (phase + ".junit.xml")),
                "exitCode": str(root / (phase + ".exit")),
                "closeAfterTests": True,
                "showReport": False,
            }
        )
        files[phase + ".junit.xml"], files[phase + ".exit"] = junit, exit_raw
        files[phase + "-settings.json"] = settings
        results[phase] = {
            **_parsed(module_rows, junit, exit_raw, outcome),
            "native_module_sha256": sha256(source),
            "module_text_verified": True,
            "client_exit_code": 0,
            "settings_sha256": sha256(settings),
        }
    engine_inventory = None
    if executed_before:
        for name, raw in engine_files.items():
            files["engine-with-tests/" + name] = raw
        engine_inventory = sorted(
            (
                {"path": name, "size": len(raw), "sha256": sha256(raw)}
                for name, raw in engine_files.items()
            ),
            key=lambda row: PureWindowsPath(row["path"]),
        )
    tests = {
        "baseline": results["baseline"],
        "candidate": results["candidate"],
        "status": results["candidate"]["status"],
        "engine_source_sha256": sha256(canonical_bytes(engine_inventory))
        if engine_inventory
        else None,
        "steps": steps,
        "isolated_infobases": True,
    }
    return tests, files


def tree(files, prefix):
    rows = [
        {"path": name[len(prefix) + 1 :], "size": len(raw), "sha256": sha256(raw)}
        for name, raw in files.items()
        if name.startswith(prefix + "/")
    ]
    if not rows:
        return None
    directories = set()
    for row in rows:
        parent = PurePosixPath(row["path"]).parent
        while str(parent) != ".":
            directories.add(str(parent))
            parent = parent.parent
    return {"files": rows, "directories": sorted(directories)}


def bundle(outcomes=("failed", "passed"), *, module_specs=(), cleanup=None):
    """A complete consistent pure-evaluator bundle with explicit constructed bytes."""
    project_id, run_id = str(uuid4()), str(uuid4())
    run_root = "C:\\state\\test-runs\\" + run_id
    engine_sha = ENGINE_SHA256
    platform_sha = "a" * 64
    module_rows = modules(*module_specs)
    profile = profile_record(
        project_id, module_rows, engine_sha256=engine_sha, platform_sha256=platform_sha
    )
    before = "\ufeff\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0430 \u0410()\r\n\u041a\u043e\u043d\u0435\u0446\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u044b\r\n".encode()
    after = before.replace(
        "\u041a\u043e\u043d\u0435\u0446".encode(),
        "\u0412\u044b\u0437\u0432\u0430\u0442\u044c\u0418\u0441\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435;\r\n\u041a\u043e\u043d\u0435\u0446".encode(),
    )
    inputs = {"Configuration.xml": b"<Configuration/>", TARGET: before}
    files = {"baseline/" + k: v for k, v in inputs.items()}
    files.update({"candidate/" + k: (after if k == TARGET else v) for k, v in inputs.items()})
    tests, outputs = runner_outputs(
        run_root, module_rows, target=TARGET, baseline=before, candidate=after, outcomes=outcomes
    )
    files.update(outputs)
    source_ref = {
        "snapshot": {"project_id": project_id, "snapshot_id": "b" * 64},
        "layer_id": "base",
        "relative_path": TARGET,
    }
    binding = {
        "source_ref": source_ref,
        "proposal_content_id": "c" * 64,
        "profile_id": profile["profile_id"],
        "platform_executable_sha256": platform_sha,
    }

    def digest(prefix):
        value = tree(files, prefix)
        return sha256(
            canonical_bytes(
                sorted(
                    ({k: r[k] for k in ("path", "size", "sha256")} for r in value["files"]),
                    key=lambda row: row["path"],
                )
            )
        )

    report = {
        "schema": 1,
        "run_id": run_id,
        **binding,
        "candidate_sha256": sha256(after),
        "baseline_input_sha256": digest("baseline"),
        "candidate_input_sha256": digest("candidate"),
        "tests": tests,
        "scratch_cleanup": cleanup or {"status": "completed", "released_logical_bytes": 0},
        "apply": {"status": "unavailable"},
        "evidence": "local_unattested",
        "runtime_dependencies": "not_fully_pinned",
    }
    report["report_sha256"] = sha256(canonical_bytes(report))
    return {
        "run_id": run_id,
        "project_id": project_id,
        "run_root": run_root,
        "record": {
            "run_id": run_id,
            "request": {"schema": 1, "run_id": run_id, "project_id": project_id, "input": binding},
            "status": "completed",
            "report": report,
        },
        "profile": profile,
        "engine_sha256": engine_sha,
        "trees": {name: tree(files, name) for name in ("baseline", "candidate", "engine-with-tests")},
        "files": {k: v for k, v in files.items() if "/" not in k},
        "targets": {
            name: files.get(name + "/" + TARGET)
            for name in ("baseline", "candidate", "baseline-roundtrip", "candidate-roundtrip")
        },
        "scratch_present": {},
    }


def resign(value):
    """Re-sign a tampered report so only the retained-byte comparison can catch it."""
    report = value["record"]["report"]
    report.pop("report_sha256")
    report["report_sha256"] = sha256(canonical_bytes(report))
    return value
