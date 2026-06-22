"""Enterprise trust center for security, CIO and procurement proof."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import (
    OPEN_FIRST_PATH_FILE,
    build_open_first_path,
    open_first_path_markdown_lines,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _score(report: dict[str, Any] | None, default: int = 0) -> int:
    if not report:
        return default
    if "score" in report:
        return _int(report.get("score"), default)
    return _int((report.get("decision") or {}).get("score"), default)


def _status(report: dict[str, Any] | None, default: str = "watch") -> str:
    if not report:
        return default
    return str(
        (report.get("decision") or {}).get("status") or report.get("status") or default
    )


def _control_status(status: str) -> str:
    if status in {"ready", "pass", "ok", "production_candidate"}:
        return "pass"
    if status in {"risk", "fail", "blocked", "critical"}:
        return "fail"
    return "warn"


def _control(
    *,
    id: str,
    title: str,
    owner: str,
    status: str,
    severity: str,
    route: str,
    evidence: str,
    acceptance: str,
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "owner": owner,
        "status": status,
        "severity": severity,
        "route": route,
        "evidence": evidence,
        "acceptance": acceptance,
        "caveats": caveats or [],
    }


def _deliverable_status(productization: dict[str, Any], *ids: str) -> str:
    statuses = {
        item.get("id"): item.get("status")
        for item in productization.get("deliverables", [])
        if item.get("id")
    }
    selected = [str(statuses.get(id) or "warn") for id in ids]
    if any(status == "fail" for status in selected):
        return "fail"
    if any(status == "warn" for status in selected):
        return "warn"
    return "pass"


def _trust_controls(
    *,
    offline_readiness: dict[str, Any],
    productization: dict[str, Any],
    security_posture: dict[str, Any],
    rights_rls: dict[str, Any],
    platform: dict[str, Any],
    evidence_artifacts: list[dict[str, Any]],
    demo_command_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
) -> list[dict[str, Any]]:
    offline_summary = offline_readiness.get("summary") or {}
    product_summary = productization.get("summary") or {}
    security_summary = security_posture.get("summary") or {}
    rights_summary = rights_rls.get("summary") or {}
    platform_checks = platform.get("checks") or []
    evidence_count = len(evidence_artifacts)
    return [
        _control(
            id="local-contour",
            title="Closed-contour execution proof",
            owner="Security / IT",
            status=_control_status(_status(offline_readiness)),
            severity="high",
            route="/offline-readiness",
            evidence=(
                f"Offline readiness: {_status(offline_readiness)} / {_score(offline_readiness)}; "
                f"external env vars: {_int(offline_summary.get('external_env'))}."
            ),
            acceptance="Run offline readiness in the customer contour with strict mode agreed by security.",
            caveats=list(offline_readiness.get("caveats") or [])[:3],
        ),
        _control(
            id="productization-gate",
            title="Enterprise delivery readiness gate",
            owner="Product owner",
            status=_control_status(_status(productization)),
            severity="high",
            route="/productization",
            evidence=(
                f"Productization: {_status(productization)} / {_score(productization)}; "
                f"findings: {_int(product_summary.get('findings'))}; "
                f"deliverables: {_int(product_summary.get('deliverables'))}."
            ),
            acceptance="Review high and medium productization findings before production rollout.",
        ),
        _control(
            id="sbom-inventory",
            title="SBOM and dependency inventory",
            owner="Security / procurement",
            status=_deliverable_status(
                productization, "sbom-inventory-guide", "sbom-inventory-service"
            ),
            severity="high",
            route="/productization",
            evidence="Productization includes SBOM inventory guide and service checks.",
            acceptance="Generate SBOM for the release candidate and attach it to the approval pack.",
        ),
        _control(
            id="offline-bundle",
            title="Offline bundle, delivery passport and verification",
            owner="Operations",
            status=_deliverable_status(
                productization, "offline-bundle-guide", "offline-bundle-service"
            ),
            severity="high",
            route="/productization",
            evidence="Offline bundle manifest service, ZIP archive and delivery passport are tracked as productization deliverables.",
            acceptance="Build and verify a portable offline archive, then review DELIVERY_PASSPORT.md before closed-contour install.",
        ),
        _control(
            id="hash-manifest",
            title="Portable evidence with SHA-256 manifest",
            owner="Release board",
            status="pass" if evidence_count else "warn",
            severity="medium",
            route="/evidence-bundle",
            evidence=f"Evidence Bundle artifacts available for this route: {evidence_count or 'on demand'}.",
            acceptance="Export JSON/Markdown artifacts and verify manifest hashes before forwarding to approval.",
        ),
        _control(
            id="rights-rls",
            title="Rights and RLS release gate",
            owner="Security / architect",
            status=_control_status(_status(rights_rls)),
            severity="high",
            route="/rights-rls",
            evidence=(
                f"Rights/RLS: {_status(rights_rls)} / {_score(rights_rls)}; "
                f"dangerous rights: {_int(rights_summary.get('dangerous_rights'))}; "
                f"findings: {_int(rights_summary.get('findings'))}."
            ),
            acceptance="Approve broad roles, dangerous rights and missing RLS caveats before go-live.",
            caveats=list(rights_rls.get("caveats") or [])[:3],
        ),
        _control(
            id="security-posture",
            title="Static 1C security posture",
            owner="Security",
            status=_control_status(_status(security_posture)),
            severity="high",
            route="/security",
            evidence=(
                f"Security posture: {_status(security_posture)} / {_score(security_posture)}; "
                f"findings: {_int(security_summary.get('findings'))}; "
                f"external exposure: {_int(security_summary.get('external_exposure'))}."
            ),
            acceptance="Review privileged mode, dynamic execution and integration findings with owners.",
            caveats=list(security_posture.get("caveats") or [])[:3],
        ),
        _control(
            id="platform-update",
            title="1C platform and update risk visibility",
            owner="Architect / operations",
            status=_control_status(_status(platform)),
            severity="medium",
            route="/platform-doctor",
            evidence=f"Platform Doctor: {_status(platform)} / {_score(platform)}; checks: {len(platform_checks)}.",
            acceptance="Attach platform, compatibility and update caveats to the pilot or release decision.",
        ),
        _control(
            id="buyer-pilot",
            title="Procurement-ready pilot route",
            owner="Director / vendor owner",
            status=_control_status(_status(pilot_launchpad)),
            severity="medium",
            route="/pilot-launchpad",
            evidence=(
                f"Pilot Launchpad: {_status(pilot_launchpad)} / {_score(pilot_launchpad)}; "
                f"Demo Command Center: {_status(demo_command_center)} / {_score(demo_command_center)}."
            ),
            acceptance="Pick a pilot offer with owner, date, acceptance criteria and approval artifacts.",
        ),
    ]


def _security_questions() -> list[dict[str, str]]:
    return [
        {
            "question": "Will private 1C code leave the customer contour?",
            "answer": "The trust route starts from local offline readiness and productization checks. External AI or services are optional integrations, not a required proof path.",
            "proof_route": "/offline-readiness",
            "artifact": "Offline Readiness + Productization Readiness",
        },
        {
            "question": "Can security inspect dependencies and bundle contents?",
            "answer": "SBOM inventory, offline bundle manifest, delivery passport and archive verification are first-class productization controls.",
            "proof_route": "/productization",
            "artifact": "SBOM + offline manifest + delivery passport",
        },
        {
            "question": "How do we prove that exported reports were not changed after the demo?",
            "answer": "Evidence Bundle returns JSON/Markdown artifacts and a SHA-256 manifest for every file in the pack.",
            "proof_route": "/evidence-bundle",
            "artifact": "Evidence Bundle manifest",
        },
        {
            "question": "Can we review roles, dangerous rights and RLS before release?",
            "answer": "Rights/RLS builds a role/object matrix, dangerous-rights signal and release gate from local EDT Rights.xml metadata.",
            "proof_route": "/rights-rls",
            "artifact": "Rights & RLS report",
        },
        {
            "question": "What happens with platform upgrades, compatibility and runtime risk?",
            "answer": "Platform Doctor and Update War Room keep platform facts, missing facts, extensions, rollback and caveats visible before approval.",
            "proof_route": "/platform-doctor",
            "artifact": "Platform Doctor / Update War Room",
        },
        {
            "question": "How does procurement compare this with another AI subscription?",
            "answer": "Business Case separates local product value from optional AI credits and ties the decision to review effort, release risk and recurring spend displacement.",
            "proof_route": "/business-case",
            "artifact": "Business Case",
        },
    ]


def _procurement_pack() -> list[dict[str, str]]:
    return [
        {
            "owner": "Security",
            "document": "Security whitepaper",
            "route": "/productization",
            "why": "Explains local contour, data handling assumptions and product hardening expectations.",
            "exit_criteria": "Security accepts pilot boundaries and lists production blockers.",
        },
        {
            "owner": "Security / procurement",
            "document": "SBOM inventory",
            "route": "/productization",
            "why": "Shows dependencies and generated inventory path for approval.",
            "exit_criteria": "SBOM attached to pilot or release candidate.",
        },
        {
            "owner": "Operations",
            "document": "Offline delivery passport",
            "route": "/productization",
            "why": "Proves package contents, hashes, signature policy and role handoff for closed-contour delivery.",
            "exit_criteria": "Archive, manifest and DELIVERY_PASSPORT.md are verified in the target environment.",
        },
        {
            "owner": "Release board",
            "document": "Evidence Bundle manifest",
            "route": "/evidence-bundle",
            "why": "Creates portable JSON/Markdown proof with SHA-256 file hashes.",
            "exit_criteria": "Approval pack contains manifest, key reports and caveats.",
        },
        {
            "owner": "Architecture board",
            "document": "Platform Doctor report",
            "route": "/platform-doctor",
            "why": "Names platform, compatibility, DBMS, tech journal and upgrade caveats.",
            "exit_criteria": "Platform and update caveats have owners or accepted risk.",
        },
        {
            "owner": "Security",
            "document": "Rights/RLS report",
            "route": "/rights-rls",
            "why": "Turns local roles and RLS signals into an auditable release gate.",
            "exit_criteria": "Dangerous rights and broad roles are approved, reduced or blocked.",
        },
        {
            "owner": "Finance / director",
            "document": "Business Case",
            "route": "/business-case",
            "why": "Explains why the buyer purchases a local evidence product instead of only renting AI.",
            "exit_criteria": "Finance accepts assumptions or provides corrected values.",
        },
        {
            "owner": "Pilot owner",
            "document": "Pilot Launchpad",
            "route": "/pilot-launchpad",
            "why": "Converts trust review into offer, owner, timeline and acceptance matrix.",
            "exit_criteria": "Pilot date, owner and first acceptance check are selected.",
        },
    ]


def _questionnaire_section(
    *,
    id: str,
    title: str,
    audience: str,
    owner: str,
    answer: str,
    proof_routes: list[str],
    evidence_files: list[str],
    acceptance: str,
    linked_controls: list[dict[str, Any]],
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    if any(item.get("status") == "fail" for item in linked_controls):
        status = "blocked"
    elif any(item.get("status") == "warn" for item in linked_controls) or caveats:
        status = "watch"
    else:
        status = "ready"
    blockers = [
        str(item.get("title") or item.get("id"))
        for item in linked_controls
        if item.get("status") == "fail"
    ]
    return {
        "id": id,
        "title": title,
        "audience": audience,
        "owner": owner,
        "status": status,
        "answer": answer,
        "proof_routes": proof_routes,
        "evidence_files": evidence_files,
        "acceptance": acceptance,
        "linked_controls": [
            str(item.get("id")) for item in linked_controls if item.get("id")
        ],
        "blockers": blockers,
        "caveats": list(caveats or [])[:5],
    }


def _security_questionnaire(
    *,
    controls: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    evidence_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    control_by_id = {str(item.get("id")): item for item in controls if item.get("id")}

    def linked(*ids: str) -> list[dict[str, Any]]:
        return [control_by_id[id] for id in ids if id in control_by_id]

    sections = [
        _questionnaire_section(
            id="data-locality",
            title="Data locality and closed contour",
            audience="Security / IT",
            owner="Security lead",
            answer=(
                "The product can be reviewed through local reports first. Private 1C code does not need to leave "
                "the customer contour for Trust Center proof; external AI remains an optional integration."
            ),
            proof_routes=["/offline-readiness", "/productization"],
            evidence_files=[
                "offline-readiness.md",
                "productization-readiness.md",
                "DELIVERY_PASSPORT.md",
            ],
            acceptance="Security confirms closed-contour pilot boundaries and any allowed external dependencies.",
            linked_controls=linked("local-contour", "productization-gate"),
            caveats=control_by_id.get("local-contour", {}).get("caveats", []),
        ),
        _questionnaire_section(
            id="sbom-offline-delivery",
            title="SBOM and offline delivery",
            audience="Security / procurement",
            owner="Product owner",
            answer=(
                "Dependencies, bundle contents, delivery passport and offline archive checks are handled as "
                "productization controls and can be attached to the approval pack."
            ),
            proof_routes=["/productization"],
            evidence_files=[
                "sbom-inventory.json",
                "offline-bundle-manifest.json",
                "DELIVERY_PASSPORT.md",
            ],
            acceptance="SBOM and offline manifest are generated for the release candidate and accepted by procurement.",
            linked_controls=linked(
                "sbom-inventory", "offline-bundle", "productization-gate"
            ),
        ),
        _questionnaire_section(
            id="artifact-integrity",
            title="Artifact integrity and forwarding",
            audience="Release board",
            owner="Release manager",
            answer=(
                "Evidence Bundle creates portable JSON/Markdown files with SHA-256 hashes, so the buyer can "
                "forward the same proof package to security, architecture and procurement."
            ),
            proof_routes=["/evidence-bundle", "/enterprise-trust-center"],
            evidence_files=[
                "evidence-bundle-manifest.json",
                "rentgen-enterprise-trust-center.md",
            ],
            acceptance="Release board verifies the manifest and archives the exact approval pack used for the decision.",
            linked_controls=linked("hash-manifest"),
            caveats=[]
            if evidence_artifacts
            else ["Evidence Bundle artifacts are generated on demand for this route."],
        ),
        _questionnaire_section(
            id="roles-rls",
            title="Roles, dangerous rights and RLS",
            audience="Security / architect",
            owner="Security architect",
            answer=(
                "Rights/RLS turns EDT metadata into a role-object matrix, dangerous-rights signal and release gate "
                "before production approval."
            ),
            proof_routes=["/rights-rls"],
            evidence_files=["rights-rls.md"],
            acceptance="Dangerous rights, broad roles and missing RLS caveats are approved, reduced or blocked.",
            linked_controls=linked("rights-rls"),
            caveats=control_by_id.get("rights-rls", {}).get("caveats", []),
        ),
        _questionnaire_section(
            id="static-security",
            title="Static security posture",
            audience="Security",
            owner="Security lead",
            answer=(
                "Static checks surface privileged mode, dynamic execution, risky integration exposure and release "
                "recommendations with owners."
            ),
            proof_routes=["/security"],
            evidence_files=["security-posture.md"],
            acceptance="Security recommendations are assigned to owners or explicitly accepted as release risk.",
            linked_controls=linked("security-posture"),
            caveats=control_by_id.get("security-posture", {}).get("caveats", []),
        ),
        _questionnaire_section(
            id="platform-upgrade",
            title="1C platform and update risk",
            audience="Architecture board",
            owner="Lead architect",
            answer=(
                "Platform Doctor and Update War Room keep compatibility, platform version, rollback and update "
                "caveats visible before rollout."
            ),
            proof_routes=["/platform-doctor", "/update-war-room"],
            evidence_files=["platform-doctor.md", "update-war-room.md"],
            acceptance="Architect accepts platform caveats, target version and rollback expectations for the pilot.",
            linked_controls=linked("platform-update"),
        ),
        _questionnaire_section(
            id="ai-subscription-displacement",
            title="AI subscription displacement",
            audience="Finance / director",
            owner="Commercial owner",
            answer=(
                "Business Case separates local product value from optional AI credits and compares the purchase "
                "against recurring subscription spend, manual review effort and incident risk."
            ),
            proof_routes=["/business-case"],
            evidence_files=["rentgen-business-case.md"],
            acceptance="Finance accepts assumptions or provides corrected values for the commercial decision.",
            linked_controls=[],
        ),
        _questionnaire_section(
            id="pilot-acceptance",
            title="Pilot acceptance and after-purchase path",
            audience="Director / vendor owner",
            owner="Pilot owner",
            answer=(
                "Pilot Launchpad converts trust review into owner, date, acceptance criteria and first activation "
                "steps, so the buyer sees what happens after purchase."
            ),
            proof_routes=["/pilot-launchpad", "/demo-command-center"],
            evidence_files=[
                "rentgen-pilot-launchpad.md",
                "rentgen-demo-command-center.md",
            ],
            acceptance="Pilot owner, date and Day 0/1/7/30 acceptance checks are selected.",
            linked_controls=linked("buyer-pilot"),
        ),
    ]
    ready_sections = len([item for item in sections if item["status"] == "ready"])
    watch_sections = len([item for item in sections if item["status"] == "watch"])
    blocked_sections = len([item for item in sections if item["status"] == "blocked"])
    status = (
        "blocked"
        if blocked_sections
        else "review_required"
        if watch_sections
        else "ready"
    )
    proof_routes = sorted(
        {route for item in sections for route in item["proof_routes"]}
    )
    send_files = [
        "rentgen-security-questionnaire.md",
        "rentgen-enterprise-trust-center.md",
        "evidence-bundle-manifest.json",
        "productization-readiness.md",
        "offline-readiness.md",
        "rights-rls.md",
        "security-posture.md",
        "platform-doctor.md",
        "rentgen-business-case.md",
        "rentgen-pilot-launchpad.md",
    ]
    verification_steps = [
        {
            "owner": "Security lead",
            "action": "Confirm closed-contour assumptions and inspect SBOM/offline delivery files.",
            "route": "/productization",
            "expected": "No unapproved data exit path remains open for the pilot.",
        },
        {
            "owner": "Release manager",
            "action": "Build Evidence Bundle and verify SHA-256 manifest before forwarding.",
            "route": "/evidence-bundle",
            "expected": "The exact JSON/Markdown files in the approval pack match the manifest.",
        },
        {
            "owner": "Lead architect",
            "action": "Accept or assign platform, update and Rights/RLS caveats.",
            "route": "/enterprise-trust-center",
            "expected": "Every blocking technical caveat has an owner, waiver or remediation route.",
        },
        {
            "owner": "Pilot owner",
            "action": "Attach the questionnaire to Day 0 pilot acceptance.",
            "route": "/pilot-launchpad",
            "expected": "Buyer sees the after-purchase path and first measurable acceptance checkpoint.",
        },
    ]
    high_risks = [item for item in risks if item.get("severity") == "high"][:5]
    return {
        "status": status,
        "ready_to_send": blocked_sections == 0,
        "ready_to_approve": blocked_sections == 0 and watch_sections == 0,
        "owner_line": (
            "Security questionnaire is ready to send with no blocking sections."
            if blocked_sections == 0
            else "Security questionnaire needs blocker resolution before buyer forwarding."
        ),
        "sections": sections,
        "ready_sections": ready_sections,
        "watch_sections": watch_sections,
        "blocked_sections": blocked_sections,
        "send_files": send_files,
        "proof_routes": proof_routes,
        "verification_steps": verification_steps,
        "high_risks": high_risks,
    }


def _install_modes() -> list[dict[str, Any]]:
    return [
        {
            "id": "closed-contour-pilot",
            "title": "Closed-contour pilot",
            "buyer": "Security + delivery lead",
            "duration": "1-7 days",
            "proof_routes": [
                "/offline-readiness",
                "/productization",
                "/evidence-bundle",
            ],
            "acceptance": "Local readiness, first evidence pack and productization caveats are accepted for pilot use.",
        },
        {
            "id": "enterprise-local-license",
            "title": "Enterprise local license",
            "buyer": "CIO + architecture board",
            "duration": "30 days",
            "proof_routes": [
                "/enterprise-trust-center",
                "/business-case",
                "/platform-doctor",
                "/rights-rls",
            ],
            "acceptance": "Security, finance and architecture agree on install mode, risks and production blockers.",
        },
        {
            "id": "vendor-rollout",
            "title": "Vendor portfolio rollout",
            "buyer": "Franchisee / implementation partner",
            "duration": "30 days",
            "proof_routes": [
                "/vendor-portfolio",
                "/pilot-launchpad",
                "/evidence-bundle",
            ],
            "acceptance": "Partner can sell a buyer-safe audit and attach Trust Center artifacts to the proposal.",
        },
    ]


def _risk_register(
    *,
    productization: dict[str, Any],
    offline_readiness: dict[str, Any],
    security_posture: dict[str, Any],
    rights_rls: dict[str, Any],
    platform: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for item in productization.get("findings", [])[:6]:
        risks.append(
            {
                "owner": "product",
                "severity": str(item.get("severity") or "medium"),
                "risk": str(
                    item.get("message") or item.get("code") or "Productization finding"
                ),
                "route": "/productization",
                "next_action": "Close or explicitly accept before production rollout.",
            }
        )
    for item in offline_readiness.get("checks", []):
        if item.get("status") == "pass":
            continue
        risks.append(
            {
                "owner": "operations",
                "severity": str(item.get("severity") or "medium"),
                "risk": str(
                    item.get("title") or item.get("id") or "Offline readiness warning"
                ),
                "route": "/offline-readiness",
                "next_action": "Re-run offline readiness in the customer contour after remediation.",
            }
        )
    for item in security_posture.get("recommendations", [])[:5]:
        risks.append(
            {
                "owner": str(item.get("owner") or "security"),
                "severity": str(item.get("severity") or "medium"),
                "risk": str(item.get("title") or "Security recommendation"),
                "route": "/security",
                "next_action": "Assign an owner and attach decision to the release gate.",
            }
        )
    for item in rights_rls.get("findings", [])[:5]:
        risks.append(
            {
                "owner": "security",
                "severity": str(item.get("severity") or "medium"),
                "risk": str(
                    item.get("message") or item.get("code") or "Rights/RLS finding"
                ),
                "route": "/rights-rls",
                "next_action": "Approve, reduce or test the role before release.",
            }
        )
    for item in platform.get("checks", []):
        if item.get("status") == "pass":
            continue
        risks.append(
            {
                "owner": "architect",
                "severity": str(item.get("severity") or "medium"),
                "risk": str(item.get("title") or item.get("id") or "Platform caveat"),
                "route": "/platform-doctor",
                "next_action": str(
                    item.get("action") or "Review platform caveat before pilot."
                ),
            }
        )
    if not risks:
        risks.append(
            {
                "owner": "lead",
                "severity": "low",
                "risk": "No blocking trust risks were found in the supplied reports.",
                "route": "/enterprise-trust-center",
                "next_action": "Keep Trust Center in the pilot approval pack.",
            }
        )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(risks, key=lambda item: order.get(str(item.get("severity")), 9))[:18]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {
            "title": "Buyer Concierge markdown",
            "filename": "rentgen-buyer-concierge.md",
            "route": "/buyer-concierge",
        },
        {
            "title": "Commercial Offer Studio markdown",
            "filename": "rentgen-commercial-offer-studio.md",
            "route": "/commercial-offer-studio",
        },
        {
            "title": "Enterprise Trust Center markdown",
            "filename": "rentgen-enterprise-trust-center.md",
            "route": "/enterprise-trust-center",
        },
        {
            "title": "Security questionnaire",
            "filename": "rentgen-security-questionnaire.md",
            "route": "/enterprise-trust-center",
        },
        {
            "title": "Evidence Bundle manifest",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
        },
        {
            "title": "Productization readiness",
            "filename": "productization-readiness.md",
            "route": "/productization",
        },
        {
            "title": "Offline delivery passport",
            "filename": "DELIVERY_PASSPORT.md",
            "route": "/productization",
        },
        {
            "title": "Offline readiness",
            "filename": "offline-readiness.md",
            "route": "/offline-readiness",
        },
        {
            "title": "Rights/RLS report",
            "filename": "rights-rls.md",
            "route": "/rights-rls",
        },
        {
            "title": "Business Case",
            "filename": "rentgen-business-case.md",
            "route": "/business-case",
        },
        {
            "title": "Pilot Launchpad",
            "filename": "rentgen-pilot-launchpad.md",
            "route": "/pilot-launchpad",
        },
    ]


def _trust_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    questionnaire: dict[str, Any],
    controls: list[dict[str, Any]],
    procurement: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": "Approve trust path",
            "route": "/enterprise-trust-center",
            "status": "watch",
            "ask": "Review locality, SBOM/offline, Rights/RLS, platform caveats and evidence retention.",
            "reason": "Trust Center prevents security objections from appearing after the commercial ask.",
        }

    trust_motion = {
        "label": "Review security questionnaire",
        "route": "/enterprise-trust-center",
        "status": str(questionnaire.get("status") or primary.get("status") or "watch"),
        "ask": str(
            questionnaire.get("owner_line")
            or "Name the artifact that unblocks enterprise approval."
        ),
        "reason": "Security/procurement needs the send-ready questionnaire before deep controls.",
    }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": "security",
                "title": "Security",
                "route": "/enterprise-trust-center",
                "status": str(questionnaire.get("status") or "watch"),
                "spark": "Security questionnaire, locality, SBOM/offline and evidence retention are in one route.",
                "proof_file": "rentgen-security-questionnaire.md",
            },
            {
                "role": "architect",
                "title": "Architect",
                "route": "/platform-doctor",
                "status": "watch",
                "spark": "Platform, update, extension and rights caveats remain visible before approval.",
                "proof_file": "platform-doctor.md",
            },
            {
                "role": "director",
                "title": "Director",
                "route": "/business-case",
                "status": "ready",
                "spark": "Local product value and trust gates support purchase instead of endless AI rent.",
                "proof_file": "rentgen-business-case.md",
            },
            {
                "role": "procurement",
                "title": "Procurement",
                "route": "/evidence-bundle",
                "status": "ready" if questionnaire.get("ready_to_send") else "watch",
                "spark": "Required files, verification steps and proof routes are forwardable.",
                "proof_file": "OPEN_FIRST.md",
            },
            {
                "role": "vendor",
                "title": "Vendor",
                "route": "/vendor-portfolio",
                "status": "watch",
                "spark": "Trust blockers can become hardening scope or paid pilot acceptance.",
                "proof_file": "rentgen-vendor-audit.md",
            },
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "security-questionnaire",
                "title": "Security questionnaire",
                "route": "/enterprise-trust-center",
                "status": str(questionnaire.get("status") or "watch"),
                "signal": f"{questionnaire.get('ready_sections', 0)} ready sections; {questionnaire.get('blocked_sections', 0)} blocked.",
                "file": "rentgen-security-questionnaire.md",
            },
            {
                "id": "productization",
                "title": "Productization",
                "route": "/productization",
                "status": "ready",
                "signal": "Offline delivery passport, SBOM/offline and package proof are part of trust handoff.",
                "file": "DELIVERY_PASSPORT.md",
            },
            {
                "id": "rights-rls",
                "title": "Rights/RLS",
                "route": "/rights-rls",
                "status": "watch",
                "signal": "Roles, objects, dangerous permissions and RLS findings are reviewable.",
                "file": "rights-rls.md",
            },
            {
                "id": "evidence-bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "Hashes, role packets, governance proof and procurement handoff are forwardable.",
                "file": "OPEN_FIRST.md",
            },
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    first_procurement = procurement[0] if procurement else {}
    if not meeting_flow:
        meeting_flow = [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick security, architect or procurement owner.",
            },
            {
                "step": 2,
                "label": "Trust",
                "route": "/enterprise-trust-center",
                "line": trust_motion["ask"],
            },
            {
                "step": 3,
                "label": "Approve",
                "route": str(first_procurement.get("route") or "/productization"),
                "line": str(
                    first_procurement.get("exit_criteria")
                    or "Name blocker or accepted artifact."
                ),
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward buyer brief, questionnaire and proof archive.",
            },
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="enterprise-trust-fallback",
        orient_title="Enterprise Trust",
        orient_route="/enterprise-trust-center",
        orient_line="Pick security, architect or procurement owner.",
        orient_status=str(
            primary.get("status") or questionnaire.get("status") or "watch"
        ),
        prove_line=str(
            questionnaire.get("owner_line")
            or "Security questionnaire is ready for review."
        ),
        close_title=str(first_procurement.get("document") or "Trust Approval"),
        close_route=str(first_procurement.get("route") or "/enterprise-trust-center"),
        close_line=str(
            first_procurement.get("exit_criteria")
            or "Name blocker or accepted artifact."
        ),
        close_file="rentgen-security-questionnaire.md",
        close_status=str(
            primary.get("status") or questionnaire.get("status") or "watch"
        ),
        verify_line="Forward buyer brief, questionnaire and proof archive.",
    )

    routes = sorted(
        {
            "/enterprise-trust-center",
            str(primary.get("route") or "/enterprise-trust-center"),
            str(trust_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item.get("route") or "") for item in controls],
            *[str(route) for route in questionnaire.get("proof_routes", [])],
        }
        - {""}
    )
    return {
        "status": str(
            brief.get("purchase_status")
            or primary.get("status")
            or questionnaire.get("status")
            or "watch"
        ),
        "score": _int(brief.get("score"), 78),
        "source": str(brief.get("source") or "enterprise-trust-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Approve trust path')}: {primary.get('ask', 'Review trust evidence before purchase.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Approve trust path"),
            "route": str(primary.get("route") or "/enterprise-trust-center"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Review trust evidence before purchase."),
            "reason": str(
                primary.get("reason")
                or "Security approval must share the same first-minute room map."
            ),
        },
        "trust_motion": trust_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": [
            "buyer-brief.md",
            "buyer-pulse.md",
            OPEN_FIRST_PATH_FILE,
            "rentgen-security-questionnaire.md",
            "rentgen-enterprise-trust-center.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
        "close_question": "Which trust artifact unblocks pilot, hardening scope or local-license approval?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Enterprise Trust Center",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        "",
        "## Trust Controls",
        "",
    ]
    for item in report["trust_controls"]:
        lines.append(
            f"- **{item['status']}** `{item['id']}` / {item['owner']} (`{item['route']}`): {item['title']}. {item['evidence']}"
        )
    lines.extend(["", "## Security Questions", ""])
    for item in report["security_questions"]:
        lines.append(
            f"- **{item['question']}** {item['answer']} (`{item['proof_route']}`)"
        )
    questionnaire = report["security_questionnaire"]
    lines.extend(
        [
            "",
            "## Security Questionnaire",
            "",
            f"Status: **{questionnaire['status']}**",
            f"Ready to send: **{questionnaire['ready_to_send']}**",
            f"Ready to approve: **{questionnaire['ready_to_approve']}**",
            f"Owner line: {questionnaire['owner_line']}",
            "",
        ]
    )
    for item in questionnaire["sections"]:
        routes = ", ".join(f"`{route}`" for route in item["proof_routes"])
        files = ", ".join(item["evidence_files"])
        lines.append(
            f"- **{item['status']}** `{item['id']}` / {item['owner']}: {item['answer']} Routes: {routes}. Files: {files}."
        )
        for blocker in item["blockers"]:
            lines.append(f"  - Blocker: {blocker}")
    lines.extend(["", "Verification steps:", ""])
    for item in questionnaire["verification_steps"]:
        lines.append(
            f"- **{item['owner']}** (`{item['route']}`): {item['action']} Expected: {item['expected']}"
        )
    bridge = report.get("trust_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Trust Room Bridge", ""])
        lines.append(
            f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**"
        )
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(
            f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/enterprise-trust-center')}`): {motion.get('ask', '')}"
        )
        trust_motion = bridge.get("trust_motion") or {}
        lines.append(
            f"- Trust motion: **{trust_motion.get('label', 'n/a')}** (`{trust_motion.get('route', '/enterprise-trust-center')}`): {trust_motion.get('ask', '')}"
        )
        lines.extend(
            open_first_path_markdown_lines(
                bridge.get("open_first_path"), default_route="/enterprise-trust-center"
            )
        )
        for item in bridge.get("role_cards", []):
            lines.append(
                f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}"
            )
        for item in bridge.get("proof_readiness", []):
            lines.append(
                f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}"
            )
        for item in bridge.get("meeting_flow", []):
            lines.append(
                f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}"
            )
    lines.extend(["", "## Procurement Pack", ""])
    for item in report["procurement_pack"]:
        lines.append(
            f"- **{item['owner']}** / {item['document']} (`{item['route']}`): {item['exit_criteria']}"
        )
    lines.extend(["", "## Risk Register", ""])
    for item in report["risk_register"]:
        lines.append(
            f"- **{item['severity']}** {item['owner']} (`{item['route']}`): {item['risk']}"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_enterprise_trust_center(
    *,
    executive: dict[str, Any],
    platform: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    offline_readiness: dict[str, Any],
    security_posture: dict[str, Any],
    rights_rls: dict[str, Any],
    demo_command_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    scenario_hub: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    evidence_artifacts: list[dict[str, Any]] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
    analysis_depth: str | None = None,
    scan_limits: dict[str, Any] | None = None,
    buyer_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a buyer-safe enterprise trust pack over implemented evidence surfaces."""

    artifacts = list(evidence_artifacts or [])
    controls = _trust_controls(
        offline_readiness=offline_readiness,
        productization=productization,
        security_posture=security_posture,
        rights_rls=rights_rls,
        platform=platform,
        evidence_artifacts=artifacts,
        demo_command_center=demo_command_center,
        pilot_launchpad=pilot_launchpad,
    )
    failed = [item for item in controls if item["status"] == "fail"]
    warned = [item for item in controls if item["status"] == "warn"]
    score = max(
        0,
        min(
            100,
            round(
                _score(offline_readiness) * 0.18
                + _score(productization) * 0.18
                + _score(security_posture) * 0.16
                + _score(rights_rls) * 0.14
                + _score(platform) * 0.12
                + _score(business_case) * 0.08
                + _score(pilot_launchpad) * 0.07
                + _score(demo_command_center) * 0.07
            )
            - len(failed) * 5
            - len(warned) * 2,
        ),
    )
    status = (
        "risk"
        if any(item["severity"] == "high" for item in failed)
        else "ready"
        if score >= 82 and not failed
        else "watch"
    )
    questions = _security_questions()
    procurement = _procurement_pack()
    modes = _install_modes()
    risks = _risk_register(
        productization=productization,
        offline_readiness=offline_readiness,
        security_posture=security_posture,
        rights_rls=rights_rls,
        platform=platform,
    )
    questionnaire = _security_questionnaire(
        controls=controls,
        risks=risks,
        evidence_artifacts=artifacts,
    )
    trust_room_bridge = _trust_room_bridge(
        buyer_brief=buyer_brief,
        questionnaire=questionnaire,
        controls=controls,
        procurement=procurement,
    )
    proof_routes = sorted(
        {route for item in controls for route in [item.get("route")] if route}
        | {item["proof_route"] for item in questions}
        | {route for mode in modes for route in mode["proof_routes"]}
        | set(questionnaire["proof_routes"])
        | set(trust_room_bridge["routes"])
    )
    source_signals = {
        "executive_status": _status(executive),
        "platform_status": _status(platform),
        "productization_status": _status(productization),
        "offline_status": _status(offline_readiness),
        "security_status": _status(security_posture),
        "rights_status": _status(rights_rls),
        "scenario_hub_status": _status(scenario_hub),
        "pilot_launchpad_status": _status(pilot_launchpad),
        "demo_command_center_status": _status(demo_command_center),
        "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
    }
    if analysis_depth:
        source_signals["analysis_depth"] = analysis_depth
    for key, value in (scan_limits or {}).items():
        source_signals[key] = value
    caveats = [
        "Enterprise Trust Center v1 composes implemented local reports; it is not a formal compliance certification.",
        "Signed installer, live IdP handshakes and customer-specific security policies remain rollout work.",
        "All production claims must be validated in the customer's own contour with agreed acceptance criteria.",
    ]
    if analysis_depth == "preview":
        caveats.append(
            "Preview depth defers full security and Rights/RLS scans; run standard or deep depth before production approval."
        )

    report: dict[str, Any] = {
        "generated_at": _now(),
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": status,
            "score": score,
            "headline": (
                "Enterprise Trust Center is ready: local contour, SBOM/offline, rights, platform and procurement proof are connected."
                if status == "ready"
                else "Enterprise Trust Center is usable, but security/productization caveats must be handled before enterprise rollout."
            ),
        },
        "summary": {
            "controls": len(controls),
            "passed_controls": len(
                [item for item in controls if item["status"] == "pass"]
            ),
            "warning_controls": len(warned),
            "failed_controls": len(failed),
            "security_questions": len(questions),
            "questionnaire_sections": len(questionnaire["sections"]),
            "questionnaire_ready": questionnaire["ready_sections"],
            "questionnaire_watch": questionnaire["watch_sections"],
            "questionnaire_blocked": questionnaire["blocked_sections"],
            "procurement_items": len(procurement),
            "install_modes": len(modes),
            "risk_items": len(risks),
            "proof_routes": len(proof_routes),
            "evidence_artifacts": len(artifacts),
            "offline_score": _score(offline_readiness),
            "productization_findings": _int(
                (productization.get("summary") or {}).get("findings")
            ),
            "security_findings": _int(
                (security_posture.get("summary") or {}).get("findings")
            ),
            "rights_findings": _int((rights_rls.get("summary") or {}).get("findings")),
            "trust_room_roles": len(trust_room_bridge["role_cards"]),
            "trust_room_proofs": len(trust_room_bridge["proof_readiness"]),
            "trust_room_steps": len(trust_room_bridge["meeting_flow"]),
            "trust_room_open_first": len(trust_room_bridge["open_first_path"]),
        },
        "trust_controls": controls,
        "security_questions": questions,
        "security_questionnaire": questionnaire,
        "trust_room_bridge": trust_room_bridge,
        "procurement_pack": procurement,
        "install_modes": modes,
        "risk_register": risks,
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": source_signals,
        "caveats": caveats,
        "download_name": "rentgen-enterprise-trust-center.md",
    }
    report["markdown"] = _markdown(report)
    return report
