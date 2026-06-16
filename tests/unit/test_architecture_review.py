from src.services.rentgen.architecture_review import build_architecture_review, infer_layer


class FakeStore:
    def module_edges(self, limit=5000, min_weight=1):
        return [
            {
                "src": "Order.Form",
                "dst": "SalesRegister",
                "weight": 25,
                "src_kind": "form",
                "dst_kind": "module",
                "src_path": "Documents/Order/Forms/Main/Ext/Form/Module.bsl",
                "dst_path": "AccumulationRegisters/Sales/Ext/ManagerModule.bsl",
                "src_domain": "Sales",
                "dst_domain": "Sales",
            },
            {
                "src": "DomainService",
                "dst": "Order.Form",
                "weight": 12,
                "src_kind": "module",
                "dst_kind": "form",
                "src_path": "CommonModules/DomainService/Ext/Module.bsl",
                "dst_path": "Documents/Order/Forms/Main/Ext/Form/Module.bsl",
                "src_domain": "Sales",
                "dst_domain": "Sales",
            },
            {
                "src": "A",
                "dst": "B",
                "weight": 300,
                "src_kind": "module",
                "dst_kind": "module",
                "src_path": "CommonModules/A/Ext/Module.bsl",
                "dst_path": "CommonModules/B/Ext/Module.bsl",
                "src_domain": "Common",
                "dst_domain": "Common",
            },
            {
                "src": "B",
                "dst": "A",
                "weight": 40,
                "src_kind": "module",
                "dst_kind": "module",
                "src_path": "CommonModules/B/Ext/Module.bsl",
                "dst_path": "CommonModules/A/Ext/Module.bsl",
                "src_domain": "Common",
                "dst_domain": "Common",
            },
        ]

    def resolve_module(self, module_ref):
        if "Order" in module_ref:
            return {"graph_modules": [{"name": "Order.Form"}]}
        return {"graph_modules": []}


def test_infer_layer_from_path_and_kind():
    edge = {
        "src": "Order.Form",
        "src_kind": "form",
        "src_path": "Documents/Order/Forms/Main/Ext/Form/Module.bsl",
    }
    assert infer_layer(edge, "src") == "presentation"

    edge = {
        "src": "SalesRegister",
        "src_kind": "module",
        "src_path": "AccumulationRegisters/Sales/Ext/ManagerModule.bsl",
    }
    assert infer_layer(edge, "src") == "data"


def test_architecture_review_flags_boundaries_cycles_and_dense_edges():
    report = build_architecture_review(FakeStore(), dense_threshold=250)
    rules = {finding["rule"] for finding in report["findings"]}

    assert "presentation_to_data" in rules
    assert "server_to_presentation" in rules
    assert "dense_coupling" in rules
    assert "cycle" in rules
    assert report["summary"]["findings"] >= 4
    assert report["summary"]["score"] < 100


def test_architecture_review_can_focus_on_changed_modules():
    report = build_architecture_review(
        FakeStore(),
        changed_modules=["Documents/Order/Forms/Main/Ext/Form/Module.bsl"],
    )

    assert report["scope"]["mode"] == "focused"
    assert report["scope"]["focus_graph_modules"] == ["Order.Form"]
    assert {edge["src"] for edge in report["top_edges"]} == {"Order.Form", "DomainService"}
