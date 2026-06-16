from src.services.rentgen.change_plan import (
    assess_ci_gate,
    build_change_plan,
    extract_diff_modules,
    render_markdown_report,
)


class FakeStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 82,
            "has_n_plus_one": True,
            "has_select_star": False,
            "reasons": [],
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {
                "object_name": "СводнаяТаблицаУХ",
                "module_kind": "module",
                "source": "module_path",
            },
            "graph_modules": [{"name": "СводнаяТаблицаУХ", "fan_in": 10}],
            "entry_subroutines": 4,
            "total": 350,
            "impacted_modules": [
                {"module": "РегламентированныйОтчет", "edges": 120},
                {"module": "АналитическиеПанели", "edges": 40},
            ],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return [
            {
                "module_path": "CommonModules/РегламентированныйОтчет/Ext/Module.bsl",
                "risk": 75,
                "has_n_plus_one": False,
                "has_select_star": True,
            }
        ]


def test_extract_diff_modules_from_unified_diff():
    diff = """diff --git a/CommonModules/X/Ext/Module.bsl b/CommonModules/X/Ext/Module.bsl
--- a/CommonModules/X/Ext/Module.bsl
+++ b/CommonModules/X/Ext/Module.bsl
+Процедура Новая()
"""

    assert extract_diff_modules(diff) == ["CommonModules/X/Ext/Module.bsl"]


def test_build_change_plan_adds_risk_driven_tests_and_gate():
    plan = build_change_plan(
        FakeStore(),
        ["CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"],
        max_edges=400,
    )
    item = plan["modules"][0]

    assert item["impact_total"] == 350
    assert item["covering_tests"]
    assert any(test["id"] == "performance-regression" for test in item["covering_tests"])

    gate = assess_ci_gate(plan, risk_threshold=70, impact_threshold=300)
    assert gate["status"] == "fail"
    assert gate["violations"]

    markdown = render_markdown_report(plan, gate)
    assert "Status: **FAIL**" in markdown
    assert "YAxUnit" in markdown

