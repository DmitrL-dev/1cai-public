"""Read-only local candidate coverage audit. Never tag, rebuild, execute or publish."""
import sys
if __name__ == "__main__":
    sys.dont_write_bytecode = True

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("release_plan_contract", ROOT / "scripts/release/release_contract.py")
contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contract)


def _cell(value, label):
    contract.fields(value, ("status", "receipt"), label)
    contract.require(value["status"] in {"passed", "failed", "missing", "not-applicable"}, "Unknown cell status")
    contract.require(value["status"] != "not-applicable", "N/A has no approved policy tuple")
    if value["status"] == "missing":
        contract.require(value["receipt"] is None, "Missing cell must not carry a receipt")
    else:
        contract.blob(value["receipt"])


def check(plan_path, evidence_root, repository=ROOT):
    """Return deterministic diagnostics; malformed inputs fail closed as ValueError.

    coverage_complete concerns the implemented delivery-cell audit. Full canonical
    requirements remain separately unqualified until experience-specific adapters
    exist. The report is never a qualification or publication receipt.
    """
    policy, policy_binding = contract.load_policy()
    plan_binding, raw = contract.checked_bytes(plan_path)
    plan = contract.strict_json(raw)
    assets, dependencies = contract.validate_plan(plan)
    contract.bind_git(plan, repository)
    evidence = contract.Evidence(evidence_root, plan)
    present = contract.inventory(evidence_root)
    expected_assets = {(p["component"], p["os"], p["arch"], p["asset_kind"])
                       for p in policy["mandatory_deliveries"]}
    asset_scopes = [(a["component"], a["os"], a["arch"], a["kind"]) for a in assets.values()]
    contract.require(len(asset_scopes) == len(set(asset_scopes))
                     and set(asset_scopes) == expected_assets, "Missing/extra/ambiguous candidate assets")
    for item in assets.values():
        evidence.read(item["blob"])
    for item in dependencies.values():
        evidence.read(item["license_file"])
    policy_tuples = {contract.tuple_key(item): item for item in policy["mandatory_deliveries"]}
    delivery_claims, used_dependencies = {}, set()
    for item in contract.sequence(plan["deliveries"], "deliveries", 32):
        contract.fields(item, (*contract.TUPLE_KEYS, "asset", "dependencies", "cells"), "delivery")
        key = contract.tuple_key(item)
        contract.require(key in policy_tuples and key not in delivery_claims, "Unknown/duplicate delivery tuple")
        wanted = policy_tuples[key]
        asset = assets.get(item["asset"])
        contract.require(asset is not None and asset["kind"] == wanted["asset_kind"]
                         and all(asset[k] == item[k] for k in ("component", "os", "arch")),
                         "Delivery asset scope differs")
        deps = contract.sequence(item["dependencies"], "delivery dependencies", 256)
        contract.require(bool(deps) and len(deps) == len(set(deps)) and set(deps) <= set(dependencies),
                         "Missing/unknown/duplicate dependency inventory")
        used_dependencies.update(deps)
        contract.require(type(item["cells"]) is dict and set(item["cells"]) <= set(contract.LIFECYCLE),
                         "Unknown lifecycle cell")
        for cell in item["cells"].values():
            _cell(cell, "lifecycle cell")
        delivery_claims[key] = item
    contract.require(used_dependencies == set(dependencies), "Unused dependency inventory")
    missing, failed, unqualified, origins = [], [], [], set()
    delivery_passes, declared_passes, total_cells = 0, 0, len(policy_tuples) * len(contract.LIFECYCLE)
    for key in sorted(policy_tuples):
        delivery = delivery_claims.get(key)
        for lifecycle in contract.LIFECYCLE:
            identity = key + "/" + lifecycle
            cell = delivery["cells"].get(lifecycle) if delivery else None
            if cell is None or cell["status"] == "missing":
                missing.append({"cell": identity, "reason": "missing-lifecycle-evidence"})
                continue
            scope = {"delivery": key, "lifecycle": lifecycle}
            successful, origin, kind = evidence.receipt(cell["receipt"], scope,
                                                       [delivery["asset"]], delivery["dependencies"])
            origins.add(origin)
            # A CI regression wrapper cannot qualify an installed lifecycle cell.
            contract.require(kind == "lifecycle-execution", "Lifecycle requires installed execution scope")
            if cell["status"] == "failed" or not successful:
                failed.append({"cell": identity, "reason": "failed-or-skipped-lifecycle"})
                continue
            declared_passes += 1
            if origin == "fixture":
                unqualified.append({"cell": identity, "reason": "fixture-is-not-installed-qualification"})
            else:
                delivery_passes += 1
    claims = {}
    for item in contract.sequence(plan["requirements"], "requirement claims", 127):
        contract.fields(item, ("id", "status", "receipt"), "requirement claim")
        identity = contract.text(item["id"], "requirement id")
        contract.require(identity in policy["requirements"] and identity not in claims,
                         "Unknown/duplicate canonical requirement")
        _cell({k: item[k] for k in ("status", "receipt")}, "requirement claim")
        claims[identity] = item
    for identity in sorted(policy["requirements"]):
        item = claims.get(identity)
        if item is None or item["status"] == "missing":
            missing.append({"cell": identity, "reason": "missing-full-criterion-evidence"})
            continue
        successful, origin, kind = evidence.receipt(item["receipt"], {"requirement": identity,
                                                       "scope": "full-criterion"}, assets, dependencies)
        origins.add(origin)
        if item["status"] == "failed" or not successful:
            failed.append({"cell": identity, "reason": "failed-or-skipped-criterion"})
        else:
            # Receipt kind / counts / digests are NOT experience-specific verification.
            # Native, model, human and product adapters must be implemented separately.
            reason = ("full-criterion-adapter-not-implemented" if kind == "full-product-criterion"
                      else "wrong-experience-kind-for-full-criterion")
            unqualified.append({"cell": identity, "reason": reason,
                                "receipt_kind": kind})
    # IDE-OS-01 / IDE-SC-22 require both client and executor on all three targets.
    # No architecture/runtime/topology choice has yet been qualified for that full
    # goal. A Windows or read-only Linux installation subset cannot erase macOS.
    for target in policy["final_targets"]:
        unqualified.append({"cell": "final-target/" + target,
                            "reason": "full-target-topology-adapter-not-implemented"})
    contract.require(present == set(evidence.bindings), "Undeclared/missing evidence files")
    coverage_complete = not missing and not failed and not unqualified
    admission_blockers = ["full-criterion-adapters-not-implemented",
                          "dependency-closure-adapter-not-implemented",
                          "stable-packaging-and-publication-not-implemented"]
    report = {
        "schema": "rentgen-release-plan-audit/1", "contract_valid": True,
        "published": False, "qualification_receipt": False,
        "source_commit": plan["source_commit"], "source_tree": plan["source_tree"],
        "record_commit": plan["record_commit"], "channel": plan["channel"],
        "component_pair": plan["component_pair"], "plan": plan_binding, "policy": policy_binding,
        "delivery": {"required_cells": total_cells, "declared_passed": declared_passes,
                     "bound_execution_passed": delivery_passes,
                     "coverage_complete": delivery_passes == total_cells},
        "canonical_requirements": 127, "ide_scenarios": 24,
        "coverage_complete": coverage_complete,
        "stable_eligible": plan["channel"] == "stable" and coverage_complete and not admission_blockers,
        "admission_blockers": admission_blockers,
        "origins": sorted(origins), "missing": missing, "failed": failed,
        "unqualified": unqualified,
        "evidence_bindings": [{"path": path, **binding}
                              for path, binding in sorted(evidence.bindings.items())],
    }
    contract.require(len(encode(report)) <= contract.MAX_JSON, "Report exceeds bound")
    return report


def encode(report):
    return (json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = check(args.plan, args.evidence_root, args.repository)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        # Do not leak input paths, arbitrary exception text, secrets or partial claims.
        result = {"schema": "rentgen-release-plan-audit/1", "contract_valid": False,
                  "coverage_complete": False, "stable_eligible": False, "published": False,
                  "qualification_receipt": False, "error": type(exc).__name__,
                  "reason": str(exc)[:240] if isinstance(exc, ValueError) else "Input unavailable or malformed"}
        sys.stdout.buffer.write(encode(result))
        return 1
    sys.stdout.buffer.write(encode(result))
    return 0 if result["coverage_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
