from src.services.rentgen import test_inventory
from src.services.rentgen.test_factory import build_test_factory


MODULE = "Documents/Order/Ext/ObjectModule.bsl"


class FakeStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 74,
            "maintainability_score": 30,
            "has_n_plus_one": False,
            "has_select_star": False,
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {
                "object_name": "Order",
                "module_kind": "ObjectModule",
                "source": "fake",
            },
            "graph_modules": [
                {
                    "name": "Order.ObjectModule",
                    "object_name": "Order",
                    "module_kind": "ObjectModule",
                    "fan_in": 1,
                    "fan_out": 2,
                    "n_subs": 3,
                    "max_complexity": 5,
                }
            ],
            "entry_subroutines": 2,
            "total": 320,
            "impacted_modules": [{"module": "CommonModules/Sales/Ext/Module.bsl", "edges": 4}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return []


class NoGraphStore(FakeStore):
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 10,
            "maintainability_score": 80,
            "has_n_plus_one": False,
            "has_select_star": False,
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {
                "object_name": "OrderForm",
                "module_kind": "FormModule",
                "source": "fake",
            },
            "graph_modules": [],
            "entry_subroutines": 0,
            "total": 0,
            "impacted_modules": [],
        }


def _make_test_inventory(tmp_path, monkeypatch):
    tests_root = tmp_path / "tests" / "bsl"
    tests_root.mkdir(parents=True)
    (tests_root / "order_tests.bsl").write_text(
        """// yaxunit
Procedure TestOrderPostingCreditLimit()
    // Order posting credit limit
EndProcedure
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(test_inventory, "ROOT", tmp_path)
    test_inventory.build_test_inventory.cache_clear()


def test_test_factory_builds_run_package_from_matrix(tmp_path, monkeypatch):
    _make_test_inventory(tmp_path, monkeypatch)

    report = build_test_factory(
        FakeStore(),
        changed_modules=[MODULE],
        client_name="ACME",
        release_name="R-42",
    )

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["changed_modules"] == 1
    assert report["summary"]["run_now"] >= 1
    assert report["summary"]["exact_tests"] == 1
    assert report["regression_pack"]
    assert any("YAxUnit" in command for command in report["commands"])
    assert "Test Factory" in report["markdown"]


def test_test_factory_degrades_to_gap_package_without_store():
    report = build_test_factory(None, changed_modules=[MODULE])

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["gaps"] == 1
    assert report["generation_tasks"]
    assert "rentgen_store_missing" in report["matrix"]["modules"][0]["gaps"][0]["kind"]


def test_test_factory_treats_unmeasured_impact_as_release_risk():
    report = build_test_factory(
        NoGraphStore(),
        changed_modules=["Documents/Order/Forms/Main/Ext/Form/Module.bsl"],
    )

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["unmeasured_impact"] == 1
    assert report["matrix"]["modules"][0]["impact_measured"] is False
    assert any("impact not measured" in item["reason"] for item in report["run_now"])
    assert any(item["title"].startswith("Impact coverage proof") for item in report["manual_checks"])
