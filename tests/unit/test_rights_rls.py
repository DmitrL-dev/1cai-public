from src.services.rentgen.metadata_graph import build_metadata_graph
from src.services.rentgen.rights_rls import build_rights_rls


def _write_role(root, name, rights_xml):
    role_dir = root / "Roles" / name / "Ext"
    role_dir.mkdir(parents=True)
    (root / "Roles" / f"{name}.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Role uuid="{name}"><Properties><Name>{name}</Name></Properties></Role></MetaDataObject>""",
        encoding="utf-8",
    )
    (role_dir / "Rights.xml").write_text(rights_xml, encoding="utf-8")


def test_rights_rls_builds_matrix_and_security_gate(tmp_path):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    _write_role(
        tmp_path,
        "Manager",
        """<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
<restriction>WHERE Department = &amp;Department</restriction>
</object></Rights>""",
    )
    build_metadata_graph.cache_clear()

    report = build_rights_rls(config_path=str(tmp_path), role_limit=20, object_limit=20)

    assert report["summary"]["roles"] == 1
    assert report["summary"]["dangerous_rights"] == 1
    assert report["summary"]["rls_rules"] == 1
    assert report["matrix"][0]["object"] == "Document.Order"
    assert report["matrix"][0]["can_write"] is True
    assert report["gate"]["block_release"] is True
    assert "Rights & RLS" in report["markdown"]


def test_rights_rls_flags_roles_without_rights(tmp_path):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    role_dir = tmp_path / "Roles" / "Viewer"
    role_dir.mkdir(parents=True)
    (tmp_path / "Roles" / "Viewer.xml").write_text(
        "<MetaDataObject><Role><Properties><Name>Viewer</Name></Properties></Role></MetaDataObject>",
        encoding="utf-8",
    )
    build_metadata_graph.cache_clear()

    report = build_rights_rls(config_path=str(tmp_path), role_limit=20, object_limit=20)

    assert report["summary"]["roles_without_rights"] == 1
    assert any(item["code"] == "role-without-rights" for item in report["findings"])


def test_rights_rls_diff_flags_added_dangerous_rights(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    baseline.mkdir()
    current.mkdir()
    for root in (baseline, current):
        (root / "Configuration.xml").write_text(
            "<MetaDataObject><Configuration><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>",
            encoding="utf-8",
        )
    _write_role(
        baseline,
        "Manager",
        """<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
</object></Rights>""",
    )
    _write_role(
        current,
        "Manager",
        """<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
</object></Rights>""",
    )
    build_metadata_graph.cache_clear()

    report = build_rights_rls(
        config_path=str(current),
        baseline_config_path=str(baseline),
        role_limit=20,
        object_limit=20,
    )

    assert report["diff"]["enabled"] is True
    assert report["diff"]["status"] == "risk"
    assert report["diff"]["summary"]["added_rights"] == 1
    assert report["diff"]["summary"]["added_dangerous_rights"] == 1
    assert any(item["code"] == "rights-diff-added-dangerous" for item in report["findings"])
    assert report["gate"]["block_release"] is True
    assert "Rights Diff" in report["markdown"]
