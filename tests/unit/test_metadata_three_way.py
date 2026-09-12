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
