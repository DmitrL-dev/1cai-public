from src.services.rentgen.demo_story import build_demo_story, build_role_report
from src.services.rentgen.intake_wizard import build_intake_plan


def _executive_report():
    return {
        "decision": {
            "status": "watch",
            "score": 78,
            "headline": "Managers should track yellow areas.",
            "release_policy": "Red areas block release.",
        },
        "kpis": {
            "modules": 120,
            "modules_with_issues": 17,
            "red_areas": 1,
            "review_queue": 3,
            "call_edges": 540,
            "offline_score": 92,
        },
        "risk_summary": {
            "high_hotspots": 2,
            "top_risks": [
                {
                    "module_path": "CommonModules/Sales/Ext/Module.bsl",
                    "risk": 84,
                    "fan_in": 21,
                }
            ],
        },
        "coverage": {"score": 89},
        "offline": {"runtime": {"environment": "development"}},
        "manager_actions": [],
    }


def test_demo_story_has_complete_role_reports_and_query_case():
    story = build_demo_story(_executive_report())

    assert story["scenario"]["id"] == "erp-slow-order-safe-release"
    assert story["scenario"]["coverage"]["status"] == "partial"
    assert "caveat" in story["scenario"]["coverage"]
    assert story["coverage_ledger"]["summary"]["items"] >= 5
    assert story["coverage_ledger"]["summary"]["caveats"] >= 1
    assert len(story["first_value"]) >= 4
    assert {item["id"] for item in story["demo_steps"]} >= {
        "open-home",
        "guided-demo",
        "developer-impact",
        "director-go-no-go",
        "evidence-bundle",
    }
    assert {item["role"] for item in story["demo_steps"]} >= {
        "all",
        "developer",
        "architect",
        "director",
        "qa",
        "ops",
        "vendor",
    }
    assert story["query_surgeon_case"]["title"] == "LEFT JOIN без ЕстьNULL"
    assert len(story["role_reports"]) == 6
    assert all(item["markdown"] and item["next_actions"] for item in story["role_reports"])
    assert {item["role"] for item in story["role_reports"]} >= {"developer", "architect", "director"}
    assert "Demo Story" in story["export"]["markdown"]
    assert "Coverage Ledger" in story["export"]["markdown"]


def test_role_report_accepts_aliases():
    report = build_role_report("руководитель", _executive_report())

    assert report["role"] == "director"
    assert report["download_name"] == "rentgen-director-report.md"
    assert "/release-readiness" in report["markdown"]


def test_intake_plan_detects_edt_source(tmp_path):
    (tmp_path / "Configuration.xml").write_text("<Configuration/>", encoding="utf-8")
    module = tmp_path / "CommonModules" / "Sales" / "Ext"
    module.mkdir(parents=True)
    (module / "Module.bsl").write_text("Процедура X()\nКонецПроцедуры", encoding="utf-8")
    form = tmp_path / "Documents" / "Order" / "Forms" / "MainForm"
    form.mkdir(parents=True)
    (form / "Form.xml").write_text("<Form/>", encoding="utf-8")
    rights = tmp_path / "Roles" / "Manager"
    rights.mkdir(parents=True)
    (rights / "Rights.xml").write_text("<Rights/>", encoding="utf-8")
    (module / "SalesTest.bsl").write_text("Процедура Test()\nКонецПроцедуры", encoding="utf-8")

    plan = build_intake_plan(str(tmp_path), "auto")

    assert plan["source"]["detected_type"] == "edt"
    assert plan["decision"]["status"] == "ready"
    assert plan["inventory"]["bsl_files"] == 2
    assert plan["inventory"]["rights_files"] == 1
    assert any(item["id"] == "platform" and item["status"] == "missing" for item in plan["coverage"])


def test_intake_plan_blocks_missing_source(tmp_path):
    plan = build_intake_plan(str(tmp_path / "missing"), "auto")

    assert plan["decision"]["status"] == "blocked"
    assert plan["decision"]["score"] == 0
    assert plan["source"]["exists"] is False
