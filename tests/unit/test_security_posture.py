import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_security_posture
from src.api.metadata_api import router
from src.services.rentgen.metadata_graph import build_metadata_graph
from src.services.rentgen.security_posture import build_security_posture


def _write_config(root):
    (root / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )

    common = root / "CommonModules" / "Security" / "Ext"
    common.mkdir(parents=True)
    (root / "CommonModules" / "Security.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><CommonModule uuid="cm"><Properties><Name>Security</Name></Properties></CommonModule></MetaDataObject>""",
        encoding="utf-8",
    )
    (common / "Module.bsl").write_text(
        """Procedure Send() Export
    SetPrivilegedMode(True);
    Execute("Message('x')");
    Conn = New HTTPConnection("example.local");
EndProcedure""",
        encoding="utf-8",
    )

    role_dir = root / "Roles" / "Admin" / "Ext"
    role_dir.mkdir(parents=True)
    (root / "Roles" / "Admin.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Role uuid="role"><Properties><Name>Admin</Name></Properties></Role></MetaDataObject>""",
        encoding="utf-8",
    )
    (role_dir / "Rights.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
<right><name>Delete</name><value>true</value></right>
</object></Rights>""",
        encoding="utf-8",
    )

    services = root / "HTTPServices"
    services.mkdir()
    (services / "Callback.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><HTTPService uuid="svc"><Properties><Name>Callback</Name></Properties></HTTPService></MetaDataObject>""",
        encoding="utf-8",
    )


def _clear_caches():
    build_metadata_graph.cache_clear()
    build_security_posture.cache_clear()


def test_security_posture_links_rights_code_and_integrations(tmp_path):
    _write_config(tmp_path)
    _clear_caches()

    report = build_security_posture(config_path=str(tmp_path), limit=20, module_limit=20)

    assert report["available"] is True
    assert report["summary"]["roles"] == 1
    assert report["summary"]["dangerous_rights"] == 2
    assert report["summary"]["privileged_code_paths"] == 1
    assert report["summary"]["dynamic_execute_paths"] == 1
    assert report["summary"]["integration_code_paths"] == 1
    assert report["summary"]["exchange_objects"] == 1
    assert report["decision"]["status"] == "warn"
    assert report["privileged_code_paths"][0]["module_path"].endswith("Module.bsl")
    assert report["integration_exposure"]["metadata_objects"][0]["type"] == "HTTPService"
    assert "Security Posture" in report["markdown"]


def test_security_posture_api_exposes_report(tmp_path, monkeypatch):
    _write_config(tmp_path)
    monkeypatch.setattr("src.services.rentgen.security_posture.DEFAULT_CONFIG_PATH", tmp_path)
    _clear_caches()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/metadata/security-posture?limit=20&module_limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["dangerous_rights"] == 2
    assert payload["summary"]["external_exposure"] == 2


@pytest.mark.asyncio
async def test_mcp_security_posture_tool_is_registered(tmp_path, monkeypatch):
    _write_config(tmp_path)
    monkeypatch.setattr("src.services.rentgen.security_posture.DEFAULT_CONFIG_PATH", tmp_path)
    _clear_caches()

    names = {tool.name for tool in TOOLS}
    report = await handle_rentgen_security_posture({"limit": 20, "module_limit": 20})

    assert "rentgen_security_posture" in names
    assert report["summary"]["privileged_code_paths"] == 1
    assert report["integration_exposure"]["code_paths"][0]["rule_id"] == "http-client"
