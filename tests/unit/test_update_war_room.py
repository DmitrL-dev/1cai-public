from src.services.rentgen.update_war_room import build_update_war_room


def test_update_war_room_builds_upgrade_plan_with_extension(tmp_path, monkeypatch):
    (tmp_path / "Configuration.xml").write_text(
        """
        <MetaDataObject>
          <Properties>
            <Name>DemoERP</Name>
            <Version>2.5</Version>
            <Vendor>1C</Vendor>
          </Properties>
        </MetaDataObject>
        """,
        encoding="utf-8",
    )
    ext = tmp_path / "Extensions" / "SalesPatch"
    ext.mkdir(parents=True)
    (ext / "Configuration.xml").write_text("<Configuration/>", encoding="utf-8")
    module = tmp_path / "CommonModules" / "Sales" / "Ext"
    module.mkdir(parents=True)
    (module / "Module.bsl").write_text(
        "Процедура X()\nКонецПроцедуры", encoding="utf-8"
    )
    monkeypatch.setenv("ONEC_PLATFORM_VERSION", "8.3.25.1000")
    monkeypatch.setenv("ONEC_DBMS", "PostgreSQL")

    report = build_update_war_room(
        None,
        config_path=str(tmp_path),
        target_platform_version="8.3.26.1000",
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        release_name="ERP update",
    )

    assert report["configuration"]["name"] == "DemoERP"
    assert report["summary"]["extensions"] == 1
    assert report["release"]["reason"] == "store-not-built"
    assert any(
        item["id"] == "extension-safety" and item["status"] == "warn"
        for item in report["checks"]
    )
    assert any(item["id"] == "release-gate" for item in report["workstreams"])
    assert "Update War Room" in report["markdown"]


def test_update_war_room_marks_missing_platform_and_source_as_risk(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("ONEC_PLATFORM_VERSION", raising=False)
    monkeypatch.delenv("ONEC_DBMS", raising=False)

    report = build_update_war_room(None, config_path=str(tmp_path / "missing"))
    checks = {item["id"]: item for item in report["checks"]}

    assert report["decision"]["status"] == "risk"
    assert checks["configuration-source"]["status"] == "fail"
    assert checks["platform-doctor"]["status"] == "fail"
    assert report["summary"]["release_impact_measured"] is False
