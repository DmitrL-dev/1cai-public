from pathlib import Path

import src.services.rentgen.metadata_insights as insights
from src.services.rentgen.metadata_graph import build_metadata_graph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_config(root: Path) -> None:
    _write(
        root / "Configuration.xml",
        """
<MetaDataObject><Configuration uuid="cfg"><Properties>
<Name>Demo</Name><Version>1.0</Version>
</Properties></Configuration></MetaDataObject>
""",
    )
    _write(
        root / "Documents" / "Order.xml",
        """
<MetaDataObject><Document uuid="doc"><Properties><Name>Order</Name></Properties></Document></MetaDataObject>
""",
    )
    _write(root / "Documents" / "Order" / "Ext" / "ObjectModule.bsl", "Procedure X()\nEndProcedure")
    _write(
        root / "Documents" / "Order" / "Forms" / "Main.xml",
        """
<MetaDataObject><Form uuid="form"><Properties><Name>Main</Name><FormType>Managed</FormType></Properties></Form></MetaDataObject>
""",
    )
    _write(
        root / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form.xml",
        """
<Form><CommandSet><ExcludedCommand>Post</ExcludedCommand><ExcludedCommand>Write</ExcludedCommand></CommandSet>
<AutoCommandBar><ChildItems><Button name="Save"><DefaultButton>false</DefaultButton></Button></ChildItems></AutoCommandBar>
</Form>
""",
    )
    _write(
        root / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form" / "Module.bsl",
        """
Процедура Check() Экспорт
Попытка
Исключение
КонецПопытки;
КонецПроцедуры
""",
    )
    _write(
        root / "Roles" / "Admin.xml",
        """
<MetaDataObject><Role uuid="role"><Properties><Name>Admin</Name></Properties></Role></MetaDataObject>
""",
    )
    _write(
        root / "Roles" / "Admin" / "Ext" / "Rights.xml",
        """
<Rights><object><name>Document.Order</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
<right><name>Delete</name><value>true</value></right>
</object></Rights>
""",
    )


def test_metadata_snapshot_diff_security_and_form_review(tmp_path, monkeypatch):
    config = tmp_path / "config"
    _build_config(config)
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr(insights, "SNAPSHOT_DIR", snapshot_dir)
    build_metadata_graph.cache_clear()

    snapshot = insights.create_metadata_snapshot("baseline", str(config))
    _write(
        config / "Catalogs" / "Customer.xml",
        "<MetaDataObject><Catalog uuid=\"cat\"><Properties><Name>Customer</Name></Properties></Catalog></MetaDataObject>",
    )
    build_metadata_graph.cache_clear()

    diff = insights.diff_metadata_snapshot(snapshot["id"], config_path=str(config))
    security = insights.security_review(str(config))
    forms = insights.review_forms("Document.Order", config_path=str(config))

    assert snapshot["summary"]["total_objects"] == 2
    assert diff["summary"]["added"] == 1
    assert diff["added"][0]["ref"] == "Catalog.Customer"
    assert security["summary"]["dangerous_rights"] == 2
    assert any(item["code"] == "dangerous-rights" for item in security["findings"])
    assert forms["summary"]["forms_reviewed"] == 1
    codes = {finding["code"] for finding in forms["forms"][0]["findings"]}
    assert "document-core-commands-excluded" in codes
    assert "form-module:empty-catch" in codes
