"""Productization readiness checks for enterprise 1cAI delivery."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DELIVERABLES: list[dict[str, Any]] = [
    {
        "id": "support-matrix",
        "category": "documentation",
        "title": "Support matrix",
        "path": "docs/productization/SUPPORT_MATRIX.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "deployment-guide",
        "category": "documentation",
        "title": "Deployment guide",
        "path": "docs/productization/DEPLOYMENT_GUIDE.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "security-whitepaper",
        "category": "documentation",
        "title": "Security whitepaper",
        "path": "docs/productization/SECURITY_WHITEPAPER.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "admin-guide",
        "category": "documentation",
        "title": "Admin guide",
        "path": "docs/productization/ADMIN_GUIDE.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "backup-restore",
        "category": "documentation",
        "title": "Backup and restore guide",
        "path": "docs/productization/BACKUP_RESTORE.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "upgrade-guide",
        "category": "documentation",
        "title": "Upgrade guide",
        "path": "docs/productization/UPGRADE_GUIDE.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "adapter-guide",
        "category": "documentation",
        "title": "Customer adapter guide",
        "path": "docs/productization/ADAPTER_GUIDE.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "enterprise-release-checklist",
        "category": "documentation",
        "title": "Enterprise release checklist",
        "path": "docs/productization/ENTERPRISE_RELEASE_CHECKLIST.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "offline-bundle-guide",
        "category": "documentation",
        "title": "Offline bundle manifest guide",
        "path": "docs/productization/OFFLINE_BUNDLE_MANIFEST.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "sbom-inventory-guide",
        "category": "documentation",
        "title": "SBOM inventory guide",
        "path": "docs/productization/SBOM_INVENTORY.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "product-research",
        "category": "strategy",
        "title": "Deep product research",
        "path": "docs/PRODUCT_RESEARCH_2026-06-15.md",
        "required": True,
        "min_bytes": 5000,
    },
    {
        "id": "coverage-map",
        "category": "strategy",
        "title": "1C Copilot coverage map",
        "path": "docs/COPILOT_COVERAGE.md",
        "required": True,
        "min_bytes": 3000,
    },
    {
        "id": "mega-plan",
        "category": "strategy",
        "title": "Autonomous implementation mega plan",
        "path": "docs/IMPLEMENTATION_MEGA_PLAN_2026-06-15.md",
        "required": True,
        "min_bytes": 3000,
    },
    {
        "id": "artifact-graph",
        "category": "governance-core",
        "title": "Internal artifact graph service",
        "path": "src/services/rentgen/artifact_graph.py",
        "required": True,
        "min_bytes": 4000,
    },
    {
        "id": "change-sets",
        "category": "governance-core",
        "title": "Change set service",
        "path": "src/services/rentgen/change_sets.py",
        "required": True,
        "min_bytes": 4000,
    },
    {
        "id": "baselines",
        "category": "governance-core",
        "title": "Baselines and review packs",
        "path": "src/services/rentgen/baselines.py",
        "required": True,
        "min_bytes": 3500,
    },
    {
        "id": "policy-engine",
        "category": "gates",
        "title": "Policy-as-code engine",
        "path": "src/services/rentgen/policy_engine.py",
        "required": True,
        "min_bytes": 4500,
    },
    {
        "id": "default-policy",
        "category": "gates",
        "title": "Default enterprise policy",
        "path": "policy/1cai-default-policy.json",
        "required": True,
        "min_bytes": 600,
    },
    {
        "id": "test-evidence",
        "category": "verification",
        "title": "Test evidence store",
        "path": "src/services/rentgen/test_evidence.py",
        "required": True,
        "min_bytes": 3500,
    },
    {
        "id": "test-runners",
        "category": "verification",
        "title": "YAxUnit/Vanessa/1C runner adapters",
        "path": "src/services/rentgen/test_runners.py",
        "required": True,
        "min_bytes": 4000,
    },
    {
        "id": "canonical-metadata",
        "category": "onec-native",
        "title": "Canonical 1C metadata model",
        "path": "src/services/rentgen/canonical_metadata.py",
        "required": True,
        "min_bytes": 4000,
    },
    {
        "id": "audit-log",
        "category": "enterprise",
        "title": "Append-only product audit log",
        "path": "src/services/audit_log.py",
        "required": True,
        "min_bytes": 2500,
    },
    {
        "id": "enterprise-iam",
        "category": "enterprise",
        "title": "Enterprise IAM readiness and project boundaries",
        "path": "src/services/enterprise_iam.py",
        "required": True,
        "min_bytes": 3500,
    },
    {
        "id": "agentic-workflows",
        "category": "agentic",
        "title": "Ask/Plan/Act/Review guardrails",
        "path": "src/services/rentgen/agentic_workflows.py",
        "required": True,
        "min_bytes": 4500,
    },
    {
        "id": "offline-bundle-service",
        "category": "packaging",
        "title": "Offline bundle manifest service",
        "path": "src/services/offline_bundle.py",
        "required": True,
        "min_bytes": 5000,
    },
    {
        "id": "sbom-inventory-service",
        "category": "packaging",
        "title": "Offline SBOM inventory service",
        "path": "src/services/sbom_inventory.py",
        "required": True,
        "min_bytes": 4000,
    },
    {
        "id": "delivery-workbench",
        "category": "ux",
        "title": "Delivery workbench UI",
        "path": "portal/src/routes/_authenticated/workbench.tsx",
        "required": True,
        "min_bytes": 3000,
    },
    {
        "id": "api-client",
        "category": "ux",
        "title": "Portal API client coverage",
        "path": "portal/src/lib/api-client.ts",
        "required": True,
        "min_bytes": 3000,
    },
    {
        "id": "phase-reviews",
        "category": "evidence",
        "title": "Per-phase review evidence",
        "path": "docs/reviews/2026-06-15_PHASE_7_AGENTIC_REVIEW.md",
        "required": True,
        "min_bytes": 500,
    },
    {
        "id": "mega-product-review",
        "category": "evidence",
        "title": "Mega product review",
        "path": "docs/reviews/2026-06-15_MEGA_PRODUCT_REVIEW.md",
        "required": True,
        "min_bytes": 3000,
    },
]

REVIEW_FILES = [
    "docs/reviews/2026-06-15_PHASE_1_ARTIFACT_GRAPH_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_1_REQUIREMENTS_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_1_CHANGE_SETS_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_1_BASELINES_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_2_POLICY_ENGINE_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_3_TEST_EVIDENCE_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_3_RUNNER_ADAPTERS_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_4_METADATA_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_5_AUDIT_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_5_ENTERPRISE_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_6_UX_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_7_AGENTIC_REVIEW.md",
    "docs/reviews/2026-06-15_PHASE_8_PRODUCTIZATION_REVIEW.md",
    "docs/reviews/2026-06-15_MEGA_PRODUCT_REVIEW.md",
    "docs/reviews/2026-06-16_PHASE_9_OFFLINE_BUNDLE_REVIEW.md",
    "docs/reviews/2026-06-16_PHASE_10_OFFLINE_ARCHIVE_REVIEW.md",
    "docs/reviews/2026-06-16_PHASE_11_SBOM_INVENTORY_REVIEW.md",
    "docs/reviews/2026-06-16_AUTONOMOUS_CONTINUATION_REVIEW.md",
]

TEST_FILES = [
    "tests/unit/test_artifact_graph.py",
    "tests/unit/test_artifacts_api.py",
    "tests/unit/test_requirements_traceability.py",
    "tests/unit/test_change_sets.py",
    "tests/unit/test_baselines_review_packs.py",
    "tests/unit/test_policy_engine.py",
    "tests/unit/test_test_evidence.py",
    "tests/unit/test_test_runners.py",
    "tests/unit/test_canonical_metadata.py",
    "tests/unit/test_product_audit_log.py",
    "tests/unit/test_enterprise_iam.py",
    "tests/unit/test_agentic_workflows.py",
    "tests/unit/test_offline_bundle.py",
    "tests/unit/test_sbom_inventory.py",
]

NON_AI_VALUE = [
    "Configuration and metadata inventory with graph traceability.",
    "Change-set risk analysis, policy gates and release readiness.",
    "Requirements-to-implementation-to-test traceability for BA and architects.",
    "Risk-driven test selection and persisted test evidence.",
    "Enterprise audit, project boundaries and approval evidence.",
    "Management workbench for readiness, blockers, coverage and residual risk.",
]

KNOWN_PRODUCT_GAPS = [
    {
        "severity": "medium",
        "code": "signed-offline-installer-missing",
        "message": "Docs define packaging, but a signed offline installer or artifact bundle is not produced by this slice.",
    },
    {
        "severity": "medium",
        "code": "live-iam-handshakes-unverified",
        "message": "OIDC/SAML/LDAP/SCIM readiness is modeled and validated, but live IdP handshakes are not exercised in tests.",
    },
    {
        "severity": "medium",
        "code": "external-runner-execution-unverified",
        "message": "YAxUnit/Vanessa/1C runner adapters are dry-run safe and import evidence, but live external execution needs customer runner validation.",
    },
    {
        "severity": "low",
        "code": "audit-hash-chain-missing",
        "message": "Audit is append-only NDJSON, but tamper-evident hash chaining and SIEM streaming are still future hardening.",
    },
    {
        "severity": "low",
        "code": "json-store-scale-limit",
        "message": "Portable JSON stores are suitable for the control-plane skeleton; large enterprise scale should move hot paths to DB-backed storage.",
    },
]


def _check_file(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    rel_path = str(spec["path"])
    abs_path = root / rel_path
    exists = abs_path.exists()
    size = abs_path.stat().st_size if exists and abs_path.is_file() else 0
    min_bytes = int(spec.get("min_bytes") or 0)
    if not exists:
        status = "fail" if spec.get("required", False) else "warn"
        message = "Required deliverable is missing." if spec.get("required", False) else "Optional deliverable is missing."
    elif size < min_bytes:
        status = "warn"
        message = f"Deliverable exists but is smaller than expected ({size} < {min_bytes} bytes)."
    else:
        status = "pass"
        message = "Deliverable is present."
    return {
        "id": spec["id"],
        "category": spec["category"],
        "title": spec["title"],
        "path": rel_path,
        "required": bool(spec.get("required", False)),
        "status": status,
        "size_bytes": size,
        "min_bytes": min_bytes,
        "message": message,
    }


def _check_named_paths(paths: list[str], *, root: Path, category: str) -> dict[str, Any]:
    checks = []
    for rel_path in paths:
        target = root / rel_path
        checks.append(
            {
                "path": rel_path,
                "status": "pass" if target.exists() else "fail",
                "size_bytes": target.stat().st_size if target.exists() and target.is_file() else 0,
            }
        )
    missing = [item["path"] for item in checks if item["status"] == "fail"]
    return {
        "category": category,
        "status": "fail" if missing else "pass",
        "total": len(checks),
        "missing": missing,
        "items": checks,
    }


def list_productization_deliverables(*, root: Path | None = None) -> dict[str, Any]:
    """Return the static productization deliverable map with file checks."""

    base = root or ROOT
    checks = [_check_file(spec, root=base) for spec in DELIVERABLES]
    by_category = Counter(item["category"] for item in checks)
    return {
        "root": str(base),
        "total": len(checks),
        "by_category": dict(sorted(by_category.items())),
        "items": checks,
    }


def productization_readiness(*, root: Path | None = None) -> dict[str, Any]:
    """Build a deterministic productization readiness report."""

    base = root or ROOT
    deliverables = list_productization_deliverables(root=base)["items"]
    reviews = _check_named_paths(REVIEW_FILES, root=base, category="reviews")
    tests = _check_named_paths(TEST_FILES, root=base, category="tests")

    findings = []
    for item in deliverables:
        if item["status"] == "fail":
            findings.append(
                {
                    "severity": "high" if item["required"] else "medium",
                    "code": "deliverable-missing",
                    "message": item["message"],
                    "path": item["path"],
                }
            )
        elif item["status"] == "warn":
            findings.append(
                {
                    "severity": "medium",
                    "code": "deliverable-thin",
                    "message": item["message"],
                    "path": item["path"],
                }
            )
    for check in (reviews, tests):
        if check["missing"]:
            findings.append(
                {
                    "severity": "high",
                    "code": f"{check['category']}-missing",
                    "message": f"Missing {len(check['missing'])} {check['category']} files.",
                    "paths": check["missing"],
                }
            )
    findings.extend(KNOWN_PRODUCT_GAPS)

    status_counts = Counter(item["status"] for item in deliverables)
    severity_counts = Counter(item["severity"] for item in findings)
    hard_fail = bool(severity_counts.get("high"))
    status = "fail" if hard_fail else ("warn" if findings else "pass")
    deliverable_score = round(
        (
            status_counts.get("pass", 0)
            + status_counts.get("warn", 0) * 0.55
            + status_counts.get("fail", 0) * 0
        )
        / max(len(deliverables), 1)
        * 100
    )
    finding_penalty = severity_counts.get("high", 0) * 20 + severity_counts.get("medium", 0) * 5 + severity_counts.get("low", 0) * 2
    score = max(0, deliverable_score - finding_penalty)
    release_decision = "blocked" if status == "fail" else ("pilot_ready" if score >= 80 else "engineering_preview")
    if status == "pass":
        release_decision = "production_candidate"

    return {
        "product": "1cAI Enterprise 1C SDLC Platform",
        "status": status,
        "release_decision": release_decision,
        "score": score,
        "summary": {
            "deliverables": len(deliverables),
            "pass": status_counts.get("pass", 0),
            "warn": status_counts.get("warn", 0),
            "fail": status_counts.get("fail", 0),
            "findings": len(findings),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "reviews_total": reviews["total"],
            "reviews_missing": len(reviews["missing"]),
            "tests_total": tests["total"],
            "tests_missing": len(tests["missing"]),
            "deliverable_score": deliverable_score,
        },
        "non_ai_value": NON_AI_VALUE,
        "deliverables": deliverables,
        "review_evidence": reviews,
        "test_evidence": tests,
        "findings": findings,
    }


def productization_markdown_report(*, root: Path | None = None) -> dict[str, Any]:
    """Render productization readiness as a compact Markdown report."""

    report = productization_readiness(root=root)
    lines = [
        "# 1cAI productization readiness",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['release_decision']}`",
        f"- Score: `{report['score']}`",
        f"- Deliverables: {report['summary']['pass']} pass / {report['summary']['warn']} warn / {report['summary']['fail']} fail",
        f"- Review files missing: {report['summary']['reviews_missing']}",
        f"- Test files missing: {report['summary']['tests_missing']}",
        "",
        "## Non-AI value",
    ]
    lines.extend(f"- {item}" for item in report["non_ai_value"])
    lines.extend(["", "## Findings"])
    if report["findings"]:
        lines.extend(
            f"- `{item['severity']}` `{item['code']}`: {item['message']}"
            for item in report["findings"]
        )
    else:
        lines.append("- No findings.")
    return {"format": "markdown", "content": "\n".join(lines), "readiness": report}
