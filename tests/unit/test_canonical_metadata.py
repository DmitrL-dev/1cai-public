import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import (
    TOOLS,
    handle_metadata_canonical_drift,
    handle_metadata_canonical_import,
    handle_metadata_canonical_objects,
    handle_metadata_rights_diff,
)
from src.api.metadata_api import router
from src.services.rentgen import artifact_graph, canonical_metadata


def _write_config(root, *, extra_attribute: bool = False, delete_right: bool = False):
    (root / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties>
<Name>Demo</Name><Version>1.0</Version><Vendor>Acme</Vendor>
</Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )
    docs = root / "Documents"
    doc_dir = docs / "Order"
    form_dir = doc_dir / "Forms" / "DocumentForm"
    (doc_dir / "Ext").mkdir(parents=True, exist_ok=True)
    (form_dir / "Ext" / "Form").mkdir(parents=True, exist_ok=True)
    attrs = '<Attribute name="Customer"/>'
    if extra_attribute:
        attrs += '<Attribute name="Amount"/>'
    (docs / "Order.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Document uuid="doc-1"><Properties>
<Name>Order</Name>
<Attributes>{attrs}</Attributes>
</Properties></Document></MetaDataObject>""",
        encoding="utf-8",
    )
    (doc_dir / "Ext" / "ObjectModule.bsl").write_text(
        "Procedure Post()\nEndProcedure", encoding="utf-8"
    )
    (doc_dir / "Forms" / "DocumentForm.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Form uuid="form-1"><Properties><Name>DocumentForm</Name><FormType>Managed</FormType></Properties></Form></MetaDataObject>""",
        encoding="utf-8",
    )
    (form_dir / "Ext" / "Form" / "Module.bsl").write_text(
        "Procedure Open()\nEndProcedure", encoding="utf-8"
    )

    role_dir = root / "Roles" / "Admin" / "Ext"
    role_dir.mkdir(parents=True, exist_ok=True)
    (root / "Roles" / "Admin.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Role uuid="role-1"><Properties><Name>Admin</Name></Properties></Role></MetaDataObject>""",
        encoding="utf-8",
    )
    delete = (
        "<right><name>Delete</name><value>true</value></right>" if delete_right else ""
    )
    (role_dir / "Rights.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
{delete}
</object></Rights>""",
        encoding="utf-8",
    )


def test_canonical_metadata_import_drift_rights_and_artifact_sync(tmp_path):
    config = tmp_path / "edt"
    config.mkdir()
    store = tmp_path / "canonical_metadata.json"
    artifacts = tmp_path / "artifact_graph.json"
    _write_config(config)

    base = canonical_metadata.import_metadata_snapshot(
        config_path=str(config),
        name="base",
        path=store,
        artifact_path=artifacts,
    )
    document = canonical_metadata.get_canonical_object("Document.Order", path=store)
    trace = artifact_graph.trace_artifact(document["id"], path=artifacts)

    _write_config(config, extra_attribute=True, delete_right=True)
    changed = canonical_metadata.import_metadata_snapshot(
        config_path=str(config),
        name="changed",
        path=store,
        artifact_path=artifacts,
    )
    drift = canonical_metadata.diff_metadata(
        before_id=base["id"], after_id=changed["id"], path=store
    )
    rights = canonical_metadata.diff_rights(
        before_id=base["id"], after_id=changed["id"], path=store
    )

    assert base["summary"]["objects"] == 2
    assert document["counts"]["attributes"] == 1
    assert {"metadata_object", "bsl_module", "form"} <= {
        node["type"] for node in trace["nodes"]
    }
    assert drift["summary"]["changed"] == 2
    assert any(item["ref"] == "Document.Order" for item in drift["changed"])
    assert rights["summary"]["changed_roles"] == 1
    assert rights["summary"]["dangerous_rights_after"] == 2


def test_metadata_api_exposes_canonical_import_objects_drift_and_rights(
    tmp_path, monkeypatch
):
    config = tmp_path / "edt"
    config.mkdir()
    _write_config(config)
    monkeypatch.setattr(
        canonical_metadata, "STORE_PATH", tmp_path / "canonical_metadata.json"
    )
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    base = client.post(
        "/api/v1/metadata/import", json={"config_path": str(config), "name": "base"}
    )
    objects = client.get("/api/v1/metadata/objects?type=Document")
    detail = client.get("/api/v1/metadata/objects/Document.Order")

    _write_config(config, extra_attribute=True, delete_right=True)
    changed = client.post(
        "/api/v1/metadata/import", json={"config_path": str(config), "name": "changed"}
    )
    snapshots = client.get("/api/v1/metadata/canonical-snapshots")
    drift = client.get(
        f"/api/v1/metadata/drift?before_id={base.json()['id']}&after_id={changed.json()['id']}"
    )
    rights = client.get(
        f"/api/v1/metadata/rights/diff?before_id={base.json()['id']}&after_id={changed.json()['id']}"
    )

    assert base.status_code == 200
    assert objects.json()["total"] == 1
    assert detail.json()["ref"] == "Document.Order"
    assert snapshots.json()["total"] == 2
    assert drift.json()["summary"]["changed"] == 2
    assert rights.json()["summary"]["changed_roles"] == 1


@pytest.mark.asyncio
async def test_mcp_canonical_metadata_tools_are_registered_and_work(
    tmp_path, monkeypatch
):
    config = tmp_path / "edt"
    config.mkdir()
    _write_config(config)
    monkeypatch.setattr(
        canonical_metadata, "STORE_PATH", tmp_path / "canonical_metadata.json"
    )
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    names = {tool.name for tool in TOOLS}
    assert {
        "metadata_canonical_import",
        "metadata_canonical_objects",
        "metadata_canonical_drift",
        "metadata_rights_diff",
    } <= names

    base = await handle_metadata_canonical_import(
        {"config_path": str(config), "name": "base"}
    )
    objects = await handle_metadata_canonical_objects({"type": "Document"})
    _write_config(config, extra_attribute=True, delete_right=True)
    changed = await handle_metadata_canonical_import(
        {"config_path": str(config), "name": "changed"}
    )
    drift = await handle_metadata_canonical_drift(
        {"before_id": base["id"], "after_id": changed["id"]}
    )
    rights = await handle_metadata_rights_diff(
        {"before_id": base["id"], "after_id": changed["id"]}
    )

    assert objects["total"] == 1
    assert drift["summary"]["changed"] == 2
    assert rights["summary"]["changed_roles"] == 1
