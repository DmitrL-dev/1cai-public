import pytest

from src.services.rentgen.metadata_graph import (
    DEFAULT_CONFIG_PATH,
    build_metadata_graph,
    get_metadata_object,
    metadata_summary,
    search_metadata,
)
from src.services.rentgen.metadata_data_governance import build_data_governance


def test_metadata_graph_reads_edt_objects_forms_modules_and_rights(tmp_path):
    root = tmp_path
    (root / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties>
<Name>Demo</Name><Synonym><item><lang>ru</lang><content>Демо</content></item></Synonym>
<Version>1.0</Version><Vendor>Acme</Vendor>
</Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )

    docs = root / "Documents"
    doc_dir = docs / "Заказ"
    form_dir = doc_dir / "Forms" / "ФормаДокумента"
    (doc_dir / "Ext").mkdir(parents=True)
    (form_dir / "Ext" / "Form").mkdir(parents=True)
    (docs / "Заказ.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Document uuid="doc-1"><Properties>
<Name>Заказ</Name>
<Synonym><item><lang>ru</lang><content>Заказ клиента</content></item></Synonym>
<Attributes><Attribute name="Контрагент"><Synonym><item><lang>ru</lang><content>Контрагент</content></item></Synonym></Attribute></Attributes>
</Properties></Document></MetaDataObject>""",
        encoding="utf-8",
    )
    (doc_dir / "Ext" / "ObjectModule.bsl").write_text("Процедура Test()\nКонецПроцедуры", encoding="utf-8")
    (doc_dir / "Forms" / "ФормаДокумента.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Form uuid="form-1"><Properties>
<Name>ФормаДокумента</Name><FormType>Managed</FormType>
</Properties></Form></MetaDataObject>""",
        encoding="utf-8",
    )
    (form_dir / "Ext" / "Form" / "Module.bsl").write_text("Процедура Open()\nКонецПроцедуры", encoding="utf-8")

    role_dir = root / "Roles" / "Администратор" / "Ext"
    role_dir.mkdir(parents=True)
    (root / "Roles" / "Администратор.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Role uuid="role-1"><Properties><Name>Администратор</Name></Properties></Role></MetaDataObject>""",
        encoding="utf-8",
    )
    (role_dir / "Rights.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Rights><object><name>Document.Заказ</name>
<right><name>Read</name><value>true</value></right>
<right><name>Update</name><value>true</value></right>
</object></Rights>""",
        encoding="utf-8",
    )

    build_metadata_graph.cache_clear()
    graph = build_metadata_graph(str(root))
    summary = metadata_summary(str(root))["summary"]
    search_results = search_metadata("заказ", config_path=str(root))
    obj = get_metadata_object("Document.Заказ", str(root))
    role = get_metadata_object("Role.Администратор", str(root))

    assert graph["available"] is True
    assert summary["total_objects"] == 2
    assert summary["total_forms"] == 1
    assert summary["total_modules"] == 2
    assert search_results[0]["ref"] == "Document.Заказ"
    assert obj is not None
    assert obj["counts"]["attributes"] == 1
    assert obj["forms"][0]["module_path"].endswith("Module.bsl")
    assert role is not None
    assert role["rights"]["rights"] == 2
    assert role["rights"]["dangerous"][0]["right"] == "Update"


def test_metadata_data_governance_reviews_registers_exchanges_and_rights(tmp_path):
    root = tmp_path
    (root / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties>
<Name>Demo</Name><Version>1.0</Version>
</Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )

    registers = root / "AccumulationRegisters"
    registers.mkdir()
    (registers / "Sales.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><AccumulationRegister uuid="reg-1"><Properties>
<Name>Sales</Name>
<Dimensions><Dimension name="Product"/></Dimensions>
<Resources><Resource name="Amount"/></Resources>
</Properties></AccumulationRegister></MetaDataObject>""",
        encoding="utf-8",
    )

    exchanges = root / "ExchangePlans"
    exchanges.mkdir()
    (exchanges / "ERP.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><ExchangePlan uuid="ex-1"><Properties><Name>ERP</Name></Properties></ExchangePlan></MetaDataObject>""",
        encoding="utf-8",
    )

    role_dir = root / "Roles" / "Admin" / "Ext"
    role_dir.mkdir(parents=True)
    (root / "Roles" / "Admin.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Role uuid="role-1"><Properties><Name>Admin</Name></Properties></Role></MetaDataObject>""",
        encoding="utf-8",
    )
    (role_dir / "Rights.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Rights><object><name>AccumulationRegister.Sales</name>
<right><name>Delete</name><value>true</value></right>
</object></Rights>""",
        encoding="utf-8",
    )

    build_metadata_graph.cache_clear()
    report = build_data_governance(config_path=str(root))

    assert report["available"] is True
    assert report["summary"]["registers"] == 1
    assert report["summary"]["exchange_objects"] == 1
    assert report["summary"]["dangerous_rights"] == 1
    assert report["objects"][0]["dimensions"][0]["name"] == "Product"
    assert any(item["code"] == "exchange-surface" for item in report["migration_findings"])


def test_edt_nested_properties_name_is_parsed(tmp_path):
    """Real EDT carries the human name at <Attribute uuid><Properties><Name>,
    not as a direct name= attr or direct <Name> child. The direct-only lookup
    skipped every element and returned 0 attributes/dimensions/resources for the
    whole config. This fixture uses the REAL EDT nesting (uuid + Properties)."""
    root = tmp_path
    (root / "Configuration.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject><Configuration uuid="cfg"><Properties>'
        "<Name>Demo</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    docs = root / "Documents"
    (docs / "Заказ" / "Ext").mkdir(parents=True)
    (docs / "Заказ.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject><Document uuid="doc-1">'
        "<Properties><Name>Заказ</Name></Properties>"
        "<ChildObjects>"
        '<Attribute uuid="a1"><Properties><Name>Контрагент</Name>'
        "<Synonym><item><lang>ru</lang><content>Контрагент</content></item></Synonym>"
        "</Properties></Attribute>"
        '<Attribute uuid="a2"><Properties><Name>Сумма</Name></Properties></Attribute>'
        '<TabularSection uuid="t1"><Properties><Name>Товары</Name></Properties></TabularSection>'
        "</ChildObjects></Document></MetaDataObject>",
        encoding="utf-8",
    )
    regs = root / "AccumulationRegisters"
    regs.mkdir()
    (regs / "Продажи.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject><AccumulationRegister uuid="reg-1">'
        "<Properties><Name>Продажи</Name></Properties>"
        "<ChildObjects>"
        '<Dimension uuid="d1"><Properties><Name>Номенклатура</Name></Properties></Dimension>'
        '<Resource uuid="r1"><Properties><Name>Количество</Name></Properties></Resource>'
        "</ChildObjects></AccumulationRegister></MetaDataObject>",
        encoding="utf-8",
    )

    build_metadata_graph.cache_clear()
    doc = get_metadata_object("Document.Заказ", str(root))
    reg = get_metadata_object("AccumulationRegister.Продажи", str(root))

    assert doc is not None
    assert doc["counts"]["attributes"] == 2
    assert {a["name"] for a in doc["attributes"]} == {"Контрагент", "Сумма"}
    assert doc["attributes"][0]["synonym"] == "Контрагент"  # nested Synonym resolved too
    assert doc["counts"]["tabular_sections"] == 1
    assert reg is not None
    assert reg["counts"]["dimensions"] == 1
    assert reg["counts"]["resources"] == 1
    assert reg["dimensions"][0]["name"] == "Номенклатура"


@pytest.mark.skipif(
    not DEFAULT_CONFIG_PATH.exists(),
    reason="unpacked 1C config (data/configs/unpacked) not available",
)
def test_real_config_objects_have_nonzero_shape():
    """On the real unpacked ERP config, at least one Document must expose
    attributes and at least one register must expose a dimension/resource."""
    build_metadata_graph.cache_clear()
    graph = build_metadata_graph()
    docs = [o for o in graph["objects"] if o["type"] == "Document"]
    reg_types = {
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
    }
    registers = [o for o in graph["objects"] if o["type"] in reg_types]
    assert docs and registers

    doc_ok = False
    for o in docs[:40]:
        e = get_metadata_object(o["ref"])
        if e and e["counts"]["attributes"] > 0 and all(a["name"].strip() for a in e["attributes"]):
            doc_ok = True
            break
    assert doc_ok, "no Document parsed any attributes — EDT <Properties><Name> bug?"

    reg_ok = False
    for o in registers[:60]:
        e = get_metadata_object(o["ref"])
        if e and (e["counts"]["dimensions"] > 0 or e["counts"]["resources"] > 0):
            reg_ok = True
            break
    assert reg_ok, "no register parsed any dimension/resource — EDT nesting bug?"
