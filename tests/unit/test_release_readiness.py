from src.services.rentgen import release_readiness as rr


class HighRiskStore:
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
            "canonical": {"object_name": "X", "module_kind": "Module", "source": "module_path"},
            "graph_modules": [{"name": "X", "fan_in": 10}],
            "entry_subroutines": 2,
            "total": 350,
            "impacted_modules": [{"module": "CriticalPath", "edges": 120}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return [
            {
                "module_path": "CommonModules/CriticalPath/Ext/Module.bsl",
                "risk": 75,
                "has_n_plus_one": False,
                "has_select_star": True,
            }
        ]


class LowRiskStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 20,
            "has_n_plus_one": False,
            "has_select_star": False,
            "reasons": [],
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {"object_name": "Order", "module_kind": "ObjectModule", "source": "module_path"},
            "graph_modules": [{"name": "Order", "fan_in": 1}],
            "entry_subroutines": 1,
            "total": 5,
            "impacted_modules": [{"module": "Order", "edges": 5}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return []


class NoGraphStore(LowRiskStore):
    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {"object_name": "OrderForm", "module_kind": "FormModule", "source": "module_path"},
            "graph_modules": [],
            "entry_subroutines": 0,
            "total": 0,
            "impacted_modules": [],
        }


def test_release_readiness_combines_gate_and_personas(monkeypatch):
    monkeypatch.setattr(rr, "get_metadata_object", lambda identifier: None)

    report = rr.build_release_readiness(
        HighRiskStore(),
        changed_modules=["CommonModules/X/Ext/Module.bsl"],
        include_forms=False,
    )

    assert report["decision"]["status"] == "fail"
    assert report["summary"]["gate_violations"] >= 2
    assert report["personas"]["manager"]["status"] == "fail"
    assert report["personas"]["qa"]["test_actions"] > 0
    assert report["metadata"]["security_review"] == {"included": False}
    assert "Status: **FAIL**" in report["markdown"]


def test_release_readiness_warns_on_form_review(monkeypatch):
    def fake_metadata_object(identifier):
        return {
            "type": "Document",
            "name": "Order",
            "ref": identifier,
            "path": "Documents/Order.xml",
            "counts": {"forms": 1, "rights": 0},
            "modules": [{"path": "Documents/Order/Ext/ObjectModule.bsl"}],
            "forms": [{"path": "Documents/Order/Forms/Main.xml"}],
            "references": [],
        }

    def fake_review_forms(identifier):
        return {
            "object": {"ref": identifier},
            "forms": [
                {
                    "form": {"name": "Main"},
                    "findings": [
                        {
                            "severity": "medium",
                            "code": "large-command-surface",
                            "message": "Review command grouping.",
                            "details": {},
                        }
                    ],
                }
            ],
            "summary": {"forms_reviewed": 1, "findings": 1},
        }

    monkeypatch.setattr(rr, "get_metadata_object", fake_metadata_object)
    monkeypatch.setattr(rr, "review_forms", fake_review_forms)

    report = rr.build_release_readiness(
        LowRiskStore(),
        changed_modules=["Documents/Order/Ext/ObjectModule.bsl"],
        include_forms=True,
    )

    assert report["decision"]["status"] == "warn"
    assert report["summary"]["form_findings"] == 1
    assert report["personas"]["architect"]["metadata_objects"] == 1
    assert report["recommended_actions"][0]["kind"] == "form-review"


def test_release_readiness_surfaces_unmeasured_impact(monkeypatch):
    monkeypatch.setattr(rr, "get_metadata_object", lambda identifier: None)

    report = rr.build_release_readiness(
        NoGraphStore(),
        changed_modules=["Documents/Order/Forms/Main/Ext/Form/Module.bsl"],
        include_forms=False,
    )

    assert report["decision"]["status"] == "warn"
    assert report["summary"]["total_impact_edges"] == 0
    assert report["summary"]["unmeasured_impact_modules"] == 1
    assert report["personas"]["architect"]["unmeasured_impact_modules"] == 1
    assert report["change_plan"]["modules"][0]["impact_measured"] is False
    assert "Unmeasured impact modules: 1" in report["markdown"]
    assert any(action["kind"] == "gate" and action["severity"] == "medium" for action in report["recommended_actions"])
