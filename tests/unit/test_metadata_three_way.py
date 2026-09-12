"""Object-level three-way planning stays UUID-bound and conservative."""

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.metadata_three_way import plan_metadata_three_way


UUID = "11111111-1111-4111-8111-111111111111"


def catalog(name, *, uuid=UUID):
    return (
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
        f'<Catalog uuid="{uuid}"><Properties><Name>{name}</Name></Properties>'
        "<ChildObjects/></Catalog></MetaDataObject>"
    ).encode()


def test_plan_binds_changes_to_uuid_and_reports_unsupported_files():
    base = {
        "Catalogs/Products.xml": catalog("Products"),
        "CommonModules/Products/Ext/Module.bsl": b"Procedure Base(); EndProcedure",
    }
    current = {
        "Catalogs/Products.xml": catalog("ProductsCustom"),
        "CommonModules/Products/Ext/Module.bsl": b"Procedure Base(); EndProcedure",
    }
    upstream = {
        "Catalogs/Products.xml": catalog("ProductsCustom"),
        "CommonModules/Products/Ext/Module.bsl": b"Procedure Upstream(); EndProcedure",
    }

    result = plan_metadata_three_way(base, current, upstream)

    assert result["scope"] == "metadata-object-v1"
    assert result["coverage"] == "partial"
    assert result["counts"]["same_change"] == 1
    object_row = next(row for row in result["objects"] if row["object_uuid"] == UUID)
    assert object_row["action"] == "same_change"
    assert object_row["current_name"] == "ProductsCustom"
    assert result["unsupported_files"] == ["CommonModules/Products/Ext/Module.bsl"]
    assert all("content" not in row for row in result["objects"])


def test_plan_detects_uuid_object_conflicts_and_path_moves():
    base = {"Catalogs/Products.xml": catalog("Products")}
    current = {"Catalogs/ProductsCustom.xml": catalog("ProductsCustom")}
    upstream = {"Catalogs/ProductsRemote.xml": catalog("ProductsRemote")}

    result = plan_metadata_three_way(base, current, upstream)
    row = result["objects"][0]
    assert row["action"] == "conflict"
    assert row["base_path"] == "Catalogs/Products.xml"
    assert row["current_path"] == "Catalogs/ProductsCustom.xml"
    assert row["upstream_path"] == "Catalogs/ProductsRemote.xml"


def test_plan_rejects_duplicate_object_uuid_in_one_tree():
    duplicate = {
        "Catalogs/A.xml": catalog("A"),
        "Catalogs/B.xml": catalog("B"),
    }
    with pytest.raises(CoreError, match="UUID"):
        plan_metadata_three_way(duplicate, {}, {})


def test_plan_rejects_invalid_metadata_xml_object_uuid():
    invalid = {
        "Catalogs/Products.xml": catalog("Products", uuid="bad-uuid"),
    }
    with pytest.raises(CoreError, match="UUID"):
        plan_metadata_three_way(invalid, {}, {})


def test_plan_rejects_xml_dtd_and_entity_declarations():
    invalid = {
        "Catalogs/Products.xml": (
            b'<!DOCTYPE MetaDataObject [<!ENTITY bomb "Products">]>'
            b'<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
            b'<Catalog uuid="11111111-1111-4111-8111-111111111111">'
            b"<Properties><Name>&bomb;</Name></Properties></Catalog></MetaDataObject>"
        )
    }

    with pytest.raises(CoreError, match="DTD|ENTITY"):
        plan_metadata_three_way(invalid, {}, {})


def test_plan_reports_disjoint_property_changes_without_resolving_object():
    base = {
        "Catalogs/Products.xml": catalog("Products").replace(
            b"</Properties>", b"<Code>CAT</Code></Properties>"
        )
    }
    current = {
        "Catalogs/Products.xml": catalog("ProductsCustom").replace(
            b"</Properties>", b"<Code>CAT</Code></Properties>"
        )
    }
    upstream = {
        "Catalogs/Products.xml": catalog("Products").replace(
            b"<Code>CAT</Code>", b"<Code>ITEM</Code>"
        )
    }

    result = plan_metadata_three_way(base, current, upstream)
    row = result["objects"][0]

    assert row["action"] == "conflict"
    assert row["property_mergeability"] == "disjoint_changes"
    changes = {item["property_name"]: item for item in row["property_changes"]}
    assert changes["Name"]["action"] == "keep_current"
    assert changes["Code"]["action"] == "take_upstream"
    assert all("value" not in item for item in row["property_changes"])


def test_plan_marks_same_property_change_as_same_change():
    base = {"Catalogs/Products.xml": catalog("Products")}
    current = {"Catalogs/Products.xml": catalog("ProductsCustom")}
    upstream = {"Catalogs/Products.xml": catalog("ProductsCustom")}

    row = plan_metadata_three_way(base, current, upstream)["objects"][0]

    assert row["property_mergeability"] == "same_change"
    assert row["property_changes"][0]["property_name"] == "Name"
    assert row["property_changes"][0]["action"] == "same_change"


def test_plan_does_not_call_unscoped_xml_change_a_path_only_change():
    base = {"Catalogs/Products.xml": catalog("Products")}
    current = {
        "Catalogs/Products.xml": catalog("Products").replace(
            b"<ChildObjects/>", b"<ChildObjects><Attribute/></ChildObjects>"
        )
    }
    upstream = current.copy()

    row = plan_metadata_three_way(base, current, upstream)["objects"][0]

    assert row["action"] == "same_change"
    assert row["property_mergeability"] == "unscoped_content"
    assert row["property_changes"] == []


def test_plan_marks_uuid_bound_path_move_as_path_only():
    base = {"Catalogs/Products.xml": catalog("Products")}
    current = {"Catalogs/ProductsRenamed.xml": catalog("Products")}
    upstream = {"Catalogs/ProductsRenamed.xml": catalog("Products")}

    row = plan_metadata_three_way(base, current, upstream)["objects"][0]

    assert row["action"] == "same_change"
    assert row["property_mergeability"] == "path_only"
    assert row["property_changes"] == []


def test_plan_marks_property_and_unscoped_changes_as_unscoped_content():
    base = {"Catalogs/Products.xml": catalog("Products")}
    current = {"Catalogs/Products.xml": catalog("ProductsCustom")}
    upstream = {
        "Catalogs/Products.xml": catalog("Products").replace(
            b"<ChildObjects/>", b"<ChildObjects><Attribute/></ChildObjects>"
        )
    }

    row = plan_metadata_three_way(base, current, upstream)["objects"][0]

    assert row["action"] == "conflict"
    assert row["property_mergeability"] == "unscoped_content"
    assert row["property_changes"][0]["property_name"] == "Name"
