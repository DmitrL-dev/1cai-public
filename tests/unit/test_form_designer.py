import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_form_blueprint
from src.api.metadata_api import router
from src.services.rentgen.form_designer import build_form_blueprint
from src.services.rentgen.metadata_graph import build_metadata_graph


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_config(root):
    _write(
        root / "Configuration.xml",
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>""",
    )
    _write(
        root / "Documents" / "Order.xml",
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Document uuid="doc"><Properties>
<Name>Order</Name>
<Attributes><Attribute name="Customer"><Type>CatalogRef.Customers</Type></Attribute><Attribute name="Amount"/></Attributes>
<TabularSections><TabularSection name="Goods"/></TabularSections>
</Properties></Document></MetaDataObject>""",
    )
    _write(
        root / "Documents" / "Order" / "Forms" / "Main.xml",
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Form uuid="form"><Properties><Name>Main</Name><FormType>Managed</FormType></Properties></Form></MetaDataObject>""",
    )
    _write(
        root / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form.xml",
        """<Form><AutoCommandBar><ChildItems><Button name="Write"><DefaultButton>true</DefaultButton></Button></ChildItems></AutoCommandBar></Form>""",
    )
    _write(
        root / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form" / "Module.bsl",
        "Procedure OnOpen()\nEndProcedure",
    )


def _clear_caches():
    build_metadata_graph.cache_clear()


def test_form_blueprint_generates_layout_assets_and_checks(tmp_path):
    _build_config(tmp_path)
    _clear_caches()

    report = build_form_blueprint("Document.Order", config_path=str(tmp_path))

    assert report["object"]["ref"] == "Document.Order"
    assert report["form_kind"] == "object"
    assert report["summary"]["fields"] == 2
    assert report["summary"]["tabular_sections"] == 1
    assert any(command["name"] == "Post" for command in report["commands"])
    assert "Document.Order" in report["generated_assets"]["form_xml"]
    assert "BeforeWrite" in report["generated_assets"]["form_module_bsl"]
    assert report["review"]["summary"]["forms_reviewed"] == 1
    assert report["acceptance_checks"]


def test_form_blueprint_api_exposes_report(tmp_path, monkeypatch):
    _build_config(tmp_path)
    monkeypatch.setattr("src.services.rentgen.form_designer.DEFAULT_CONFIG_PATH", tmp_path)
    _clear_caches()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/metadata/form-blueprint",
        json={"identifier": "Document.Order", "form_kind": "list", "include_review": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["form_kind"] == "list"
    assert payload["layout"]["sections"][0]["type"] == "DynamicList"
    assert payload["review"] is None


@pytest.mark.asyncio
async def test_mcp_form_blueprint_tool_is_registered(tmp_path, monkeypatch):
    _build_config(tmp_path)
    monkeypatch.setattr("src.services.rentgen.form_designer.DEFAULT_CONFIG_PATH", tmp_path)
    _clear_caches()

    names = {tool.name for tool in TOOLS}
    report = await handle_rentgen_form_blueprint({"identifier": "Document.Order"})

    assert "rentgen_form_blueprint" in names
    assert report["summary"]["fields"] == 2
    assert report["generated_assets"]["import_ready"] is False
