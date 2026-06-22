from __future__ import annotations

import pytest

from src.services.rentgen.extension_safety import build_extension_safety


def test_extension_safety_detects_risky_extension(tmp_path):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>DemoERP</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    ext = tmp_path / "Extensions" / "SalesPatch"
    module = ext / "CommonModules" / "Sales" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    module.write_text(
        """
Procedure BeforeWrite()
    SetPrivilegedMode(True);
    BeginTransaction();
EndProcedure
""",
        encoding="utf-8",
    )
    rights = ext / "Roles" / "Admin" / "Ext" / "Rights.xml"
    rights.parent.mkdir(parents=True)
    rights.write_text("<Rights>borrowed object rights</Rights>", encoding="utf-8")

    report = build_extension_safety(config_path=str(tmp_path))

    assert report["source"]["exists"] is True
    assert report["decision"]["status"] == "risk"
    assert report["summary"]["extensions"] == 1
    assert report["summary"]["modules"] == 1
    assert report["summary"]["high"] >= 1
    assert report["summary"]["rights_files"] == 1
    assert report["summary"]["borrowed_objects"] >= 1
    assert report["extensions"][0]["name"] == "SalesPatch"
    assert any(
        action["kind"] == "extension-review" for action in report["recommended_actions"]
    )
    assert "Extension Safety" in report["markdown"]


def test_extension_safety_no_extensions_is_ready_with_caveat(tmp_path):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>DemoERP</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )

    report = build_extension_safety(config_path=str(tmp_path))

    assert report["decision"]["status"] == "ready"
    assert report["summary"]["extensions"] == 0
    assert report["caveats"]


def test_extension_safety_missing_source_is_watch(tmp_path):
    # A missing source *inside* an allowed data root must degrade to watch with
    # a no-data caveat, not a hard rejection.
    report = build_extension_safety(
        config_path=str(tmp_path / "missing" / "config" / "source")
    )

    assert report["source"]["exists"] is False
    assert report["decision"]["status"] == "watch"
    assert report["decision"]["risk_score"] == 100


def test_extension_safety_rejects_path_outside_data_roots():
    # Path-traversal / arbitrary-file-read guard: an absolute path outside the
    # allowed data roots must be refused, not scanned.
    with pytest.raises(ValueError, match="outside the allowed data roots"):
        build_extension_safety(config_path=r"C:\Windows")
