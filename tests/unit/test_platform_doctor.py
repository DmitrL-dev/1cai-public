import pytest

from src.services.rentgen.platform_doctor import build_platform_doctor


def test_platform_doctor_uses_env_and_config(tmp_path, monkeypatch):
    (tmp_path / "Configuration.xml").write_text(
        """
        <MetaDataObject>
          <Properties>
            <Name>DemoERP</Name>
            <Version>2.5.1</Version>
            <CompatibilityMode>Version8_3_22</CompatibilityMode>
          </Properties>
        </MetaDataObject>
        """,
        encoding="utf-8",
    )
    tj = tmp_path / "tj.log"
    tj.write_text("TLOCK", encoding="utf-8")
    monkeypatch.setenv("ONEC_PLATFORM_VERSION", "8.3.25.1000")
    monkeypatch.setenv("ONEC_TARGET_PLATFORM_VERSION", "8.3.26.1000")
    monkeypatch.setenv("ONEC_DBMS", "PostgreSQL")
    monkeypatch.setenv("ONEC_CLUSTER", "prod-cluster")
    monkeypatch.setenv("ONEC_TECH_JOURNAL_PATH", str(tj))
    monkeypatch.setenv("ONEC_OPENMETRICS_URL", "http://localhost:9090/metrics")

    report = build_platform_doctor(config_path=str(tmp_path))

    assert report["inventory"]["platform_version"] == "8.3.25.1000"
    assert report["inventory"]["target_platform_version"] == "8.3.26.1000"
    assert report["inventory"]["dbms"] == "PostgreSQL"
    assert report["decision"]["score"] >= 70
    assert any(item["id"] == "openmetrics-8325" and item["available"] for item in report["capabilities"])
    assert "Platform Doctor" in report["markdown"]


def test_platform_doctor_keeps_unknowns_as_warnings(tmp_path, monkeypatch):
    monkeypatch.delenv("ONEC_PLATFORM_VERSION", raising=False)
    monkeypatch.delenv("ONEC_TARGET_PLATFORM_VERSION", raising=False)
    monkeypatch.delenv("ONEC_DBMS", raising=False)
    monkeypatch.delenv("ONEC_TECH_JOURNAL_PATH", raising=False)

    report = build_platform_doctor(config_path=str(tmp_path / "missing"))
    check_by_id = {item["id"]: item for item in report["checks"]}

    assert report["decision"]["status"] == "risk"
    assert check_by_id["platform-version"]["status"] == "warn"
    assert check_by_id["compatibility-mode"]["status"] == "warn"
    assert "Unknown platform facts" in "\n".join(report["caveats"])
    assert any("ONEC_PLATFORM_VERSION" in item for item in report["upgrade"]["checklist"])


def test_platform_doctor_rejects_path_outside_data_roots():
    # Path-traversal / arbitrary-file-read guard: an absolute path outside the
    # allowed data roots must be refused, not read.
    with pytest.raises(ValueError, match="outside the allowed data roots"):
        build_platform_doctor(config_path=r"C:\Windows")
