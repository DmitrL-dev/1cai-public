from src.services.rentgen.vendor_portfolio import (
    build_vendor_portfolio,
    build_vendor_portfolio_book,
)


def _executive_report(red_areas: int = 0, score: int = 86):
    return {
        "decision": {"status": "ready", "score": score},
        "kpis": {
            "modules": 120,
            "modules_with_issues": 8,
            "red_areas": red_areas,
            "review_queue": 3,
        },
        "risk_summary": {
            "top_risks": [
                {
                    "module_path": "CommonModules/Sales/Ext/Module.bsl",
                    "risk": 77,
                    "fan_in": 18,
                    "domain": "Sales",
                    "reasons": [],
                }
            ]
        },
    }


def _platform_report(status: str = "ready", score: int = 90):
    return {
        "decision": {"status": status, "score": score},
        "inventory": {
            "configuration_name": "DemoERP",
            "configuration_version": "2.5",
        },
        "checks": [
            {
                "id": "platform-version",
                "status": "pass",
                "severity": "high",
            }
        ],
        "caveats": [],
    }


def _intake_plan(score: int = 80):
    return {
        "decision": {"status": "ready", "score": score},
        "caveats": ["Rights coverage is partial"],
    }


def _buyer_brief():
    return {
        "status": "ready",
        "score": 87,
        "purchase_status": "ready",
        "source": "management-buyer-brief",
        "room_line": "Ask for local license: move from proof to product. AI baseline: 4 320 000 RUB over three years.",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/board-pack",
            "status": "ready",
            "ask": "Move from demo proof to a local product purchase.",
            "reason": "Buyer pulse is ready.",
        },
        "role_cards": [
            {
                "role": "developer",
                "title": "Developer",
                "route": "/change",
                "status": "ready",
                "spark": "impact proof",
                "proof_file": "rentgen-developer-report.md",
            },
            {
                "role": "architect",
                "title": "Architect",
                "route": "/platform-doctor",
                "status": "ready",
                "spark": "platform proof",
                "proof_file": "rentgen-architect-report.md",
            },
            {
                "role": "director",
                "title": "Director",
                "route": "/board-pack",
                "status": "ready",
                "spark": "money proof",
                "proof_file": "board-pack.md",
            },
            {
                "role": "security",
                "title": "Security",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "spark": "trust proof",
                "proof_file": "rentgen-security-questionnaire.md",
            },
            {
                "role": "vendor",
                "title": "Vendor",
                "route": "/vendor-portfolio",
                "status": "ready",
                "spark": "audit proof",
                "proof_file": "vendor-portfolio.md",
            },
        ],
        "proof_readiness": [
            {
                "id": "bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "hashed proof",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "approval",
                "title": "Approval gates",
                "route": "/approvals",
                "status": "ready",
                "signal": "governance proof",
                "file": "governance-proof.md",
            },
            {
                "id": "audit",
                "title": "Audit / SIEM",
                "route": "/audit",
                "status": "ready",
                "signal": "hash chain",
                "file": "rentgen-audit-siem.jsonl",
            },
            {
                "id": "trust",
                "title": "Enterprise Trust",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "signal": "questionnaire",
                "file": "rentgen-security-questionnaire.md",
            },
        ],
        "meeting_flow": [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick the role.",
            },
            {
                "step": 2,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show proof.",
            },
            {
                "step": 3,
                "label": "Ask",
                "route": "/board-pack",
                "line": "Ask for purchase.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward packet.",
            },
        ],
    }


def test_vendor_portfolio_builds_pre_sale_work_packages():
    report = build_vendor_portfolio(
        executive=_executive_report(),
        platform=_platform_report(),
        intake=_intake_plan(),
        buyer_brief=_buyer_brief(),
        client_name="ACME ERP",
    )

    assert report["client"]["name"] == "ACME ERP"
    assert report["client"]["configuration"] == "DemoERP"
    assert report["decision"]["status"] == "ready"
    assert report["portfolio"]["clients"] == 1
    assert report["portfolio"]["vendor_room_roles"] == 5
    assert report["portfolio"]["vendor_room_proofs"] == 4
    assert report["portfolio"]["vendor_room_steps"] == 4
    assert report["portfolio"]["vendor_room_open_first"] == 4
    assert (
        report["portfolio"]["coverage_caveats"]
        == report["coverage_ledger"]["summary"]["caveats"]
    )
    assert report["coverage_ledger"]["summary"]["items"] >= 8
    assert {item["id"] for item in report["commercial_signals"]} >= {
        "risk-audit",
        "platform-upgrade",
        "release-factory",
    }
    assert {item["id"] for item in report["work_packages"]} >= {
        "connect",
        "risk-burn-down",
        "platform-readiness",
    }
    assert report["deal_board"]["recommended_motion"]
    assert report["deal_board"]["next_step"]["to"] in {
        "/business-case",
        "/commercial-offer-studio",
        "/pilot-launchpad",
    }
    assert len(report["deal_board"]["proof_packet"]) == 4
    assert report["vendor_room_bridge"]["source"] == "management-buyer-brief"
    assert report["vendor_room_bridge"]["coverage_ledger"]["summary"]["items"] >= 8
    assert report["vendor_room_bridge"]["files"][:3] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
    ]
    assert [
        item["stage"] for item in report["vendor_room_bridge"]["open_first_path"]
    ] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in report["vendor_room_bridge"]["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert "Vendor Audit" in report["markdown"]
    assert "Deal Board" in report["markdown"]
    assert "Vendor Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
    assert "Coverage Ledger" in report["markdown"]


def test_vendor_portfolio_does_not_hide_red_or_platform_risk():
    report = build_vendor_portfolio(
        executive=_executive_report(red_areas=2, score=76),
        platform=_platform_report(status="risk", score=58),
        intake=_intake_plan(score=65),
    )

    assert report["decision"]["status"] == "risk"
    assert report["portfolio"]["red_areas"] == 2
    assert report["vendor_room_bridge"]["source"] == "vendor-portfolio-derived"
    assert report["vendor_room_bridge"]["files"][2] == "open-first-path.md"
    assert any(item["priority"] == "P0" for item in report["work_packages"])
    assert "Commercial estimates" in "\n".join(report["caveats"])


def test_vendor_portfolio_book_aggregates_multiple_audits():
    ready = build_vendor_portfolio(
        executive=_executive_report(),
        platform=_platform_report(),
        intake=_intake_plan(),
        client_name="Ready client",
    )
    risky = build_vendor_portfolio(
        executive=_executive_report(red_areas=2, score=76),
        platform=_platform_report(status="risk", score=58),
        intake=_intake_plan(score=65),
        client_name="Risk client",
    )

    report = build_vendor_portfolio_book(
        audits=[ready, risky],
        portfolio_name="Partner pipeline",
    )

    assert report["portfolio"]["name"] == "Partner pipeline"
    assert report["portfolio"]["clients"] == 2
    assert report["portfolio"]["risk"] == 1
    assert report["decision"]["status"] == "risk"
    assert report["opportunities"]
    assert report["decision_board"]["next_commercial_move"]["to"] == "/pilot-launchpad"
    assert len(report["decision_board"]["segments"]) == 3
    assert any(segment["clients"] for segment in report["decision_board"]["segments"])
    assert len(report["decision_board"]["offer_sequence"]) == 3
    assert any(item["to"] == "/business-case" for item in report["next_actions"])
    assert "Vendor Portfolio" in report["markdown"]
    assert "Portfolio Decision Board" in report["markdown"]
