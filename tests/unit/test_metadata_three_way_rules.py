"""Owner, UUID, resource and namespace rules fail closed on unknown shapes."""

import copy
import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.metadata_three_way import (
    materialize_metadata_three_way,
    plan_metadata_three_way,
)


UUID = "11111111-1111-4111-8111-111111111111"
OTHER_UUID = "22222222-2222-4222-8222-222222222222"
MD_NS = "http://v8.1c.ru/8.3/MDClasses"
OWNER = "Catalogs/Products.xml"
PAYLOAD = b"PRIVATE resource payload"


def metadata(
    kind="Catalog",
    name="Products",
    *,
    identity=UUID,
    code="0",
    root_ns=MD_NS,
    node_ns=MD_NS,
):
    return (
        f'<m:MetaDataObject xmlns:m="{root_ns}" xmlns:o="{node_ns}">'
        f'<o:{kind} uuid="{identity}"><o:Properties><o:Name>{name}</o:Name>'
        f"<o:Code>{code}</o:Code></o:Properties><o:ChildObjects/></o:{kind}>"
        "</m:MetaDataObject>"
    ).encode()


def triple(base, current=None, upstream=None):
    return [
        base,
        base if current is None else current,
        base if upstream is None else upstream,
    ]


def plan(*trees):
    return plan_metadata_three_way(*triple(*trees))


def scopes(*trees):
    return plan(*trees)["semantics"]["scopes"]


def blocked(*trees, code="THREE_WAY_CONFLICT"):
    inputs = triple(*trees)
    before = copy.deepcopy(inputs)
    with pytest.raises(CoreError) as caught:
        materialize_metadata_three_way(*inputs)
    error = caught.value
    assert error.code == code
    assert inputs == before
    assert "candidate" not in error.details
    assert "PRIVATE" not in json.dumps(error.to_dict("request"))
    return error


def reasons(error):
    return {row["reason"] for row in error.details["blocking_scopes"]}


@pytest.mark.parametrize(
    "scope",
    [
        "Ext/Help.xml",
        "Ext/Help/ru.html",
        "Ext/Predefined.xml",
        "EXT/help.XML",
    ],
)
def test_unknown_owner_bound_resource_blocks_even_when_unchanged(scope):
    raw = b"<Help>PRIVATE</Help>" if scope.lower().endswith(".xml") else PAYLOAD
    tree = {OWNER: metadata(), "Catalogs/Products/" + scope: raw}

    rows = scopes(tree)

    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "resource"
    assert (row["object_type"], row["object_uuid"]) == ("Catalog", UUID)
    assert row["scope"] == scope
    assert row["action"] == "unchanged"
    assert row["granularity"] == "atomic_bytes"
    assert row["status"] == "unsupported"
    assert row["reason"] == "resource_kind_unsupported"
    error = blocked(tree)
    assert error.details["blocking_scopes"] == [
        {"object_uuid": UUID, "scope": scope, "reason": "resource_kind_unsupported"}
    ]


def test_nested_form_resource_binds_to_form_uuid_not_parent_catalog():
    path = "Catalogs/Products/Forms/Item/Ext/Form/Help/ru.html"
    tree = {
        OWNER: metadata(),
        "Catalogs/Products/Forms/Item.xml": metadata(
            "Form", "Item", identity=OTHER_UUID
        ),
        path: PAYLOAD,
    }
    row = scopes(tree)[0]
    assert (row["object_type"], row["object_uuid"]) == ("Form", OTHER_UUID)
    assert row["scope"] == "Ext/Form/Help/ru.html"
    assert row["reason"] == "resource_kind_unsupported"

    del tree["Catalogs/Products/Forms/Item.xml"]
    row = scopes(tree)[0]
    assert row["object_uuid"] is None
    assert row["reason"] == "owner_not_found"


@pytest.mark.parametrize(
    "path",
    [
        "Catalogs/Missing/Ext/Predefined.xml",
        "Ext/HomePageWorkArea.xml",
        "ext/ClientApplicationInterface.xml",
    ],
)
def test_resource_without_owner_descriptor_is_owner_not_found(path):
    tree = {OWNER: metadata(), path: b"<Resource>PRIVATE</Resource>"}
    rows = scopes(tree)
    assert len(rows) == 1
    assert rows[0]["kind"] == "resource"
    assert rows[0]["object_uuid"] is None
    assert rows[0]["scope"] == path
    assert rows[0]["status"] == "unsupported"
    assert rows[0]["reason"] == "owner_not_found"
    assert reasons(blocked(tree)) == {"owner_not_found"}


@pytest.mark.parametrize("with_resource", [False, True])
def test_changed_resource_blocks_an_otherwise_qualified_property_merge(
    with_resource,
):
    resource = "Catalogs/Products/Ext/Predefined.xml"
    base = {OWNER: metadata()}
    current = {OWNER: metadata(name="Local")}
    upstream = {OWNER: metadata(code="1")}
    if with_resource:
        base[resource] = upstream[resource] = b"<Items>PRIVATE 0</Items>"
        current[resource] = b"<Items>PRIVATE 1</Items>"

    if not with_resource:
        result = materialize_metadata_three_way(base, current, upstream)
        assert result["status"] == "ready"
        assert result["counts"]["merged_objects"] == 1
        return
    row = scopes(base, current, upstream)[0]
    assert row["action"] == "keep_current"
    assert row["reason"] == "resource_kind_unsupported"
    assert reasons(blocked(base, current, upstream)) == {"resource_kind_unsupported"}


@pytest.mark.parametrize("upstream_resource", [False, True])
def test_owner_move_cannot_leave_an_unknown_resource_orphaned(upstream_resource):
    base = {OWNER: metadata()}
    current = {"Catalogs/Renamed.xml": metadata(name="Renamed")}
    upstream = {OWNER: metadata(code="1")}
    if upstream_resource:
        upstream["Catalogs/Products/Ext/Help.xml"] = b"<Help>PRIVATE</Help>"

    if not upstream_resource:
        result = materialize_metadata_three_way(base, current, upstream)
        assert set(result["candidate"]) == {"Catalogs/Renamed.xml"}
        return
    error = blocked(base, current, upstream)
    assert error.details["blocking_scopes"] == [
        {
            "object_uuid": UUID,
            "scope": "Ext/Help.xml",
            "reason": "resource_kind_unsupported",
        }
    ]


def test_files_outside_ext_directories_remain_ordinary_path_bytes():
    base = {
        OWNER: metadata(),
        "ConfigDumpInfo.xml": b"<ConfigDumpInfo>0</ConfigDumpInfo>",
        "notes.txt": b"base",
        "Catalogs/Products/Extension/readme.txt": b"same",
        "Catalogs/Products/External/Ext.txt": b"same",
        "Docs/Ext": b"same",
    }
    current = {**base, "notes.txt": b"current"}
    upstream = {**base, "ConfigDumpInfo.xml": b"<ConfigDumpInfo>1</ConfigDumpInfo>"}

    plan_result = plan(base, current, upstream)
    assert plan_result["semantics"]["scopes"] == []
    result = materialize_metadata_three_way(base, current, upstream)
    assert result["candidate"] == {
        **base,
        "notes.txt": b"current",
        "ConfigDumpInfo.xml": b"<ConfigDumpInfo>1</ConfigDumpInfo>",
    }


@pytest.mark.parametrize(
    "root_ns,node_ns,reason",
    [
        (MD_NS, MD_NS, None),
        ("urn:foreign", MD_NS, "owner_namespace_unsupported"),
        (MD_NS, "urn:foreign", "owner_namespace_unsupported"),
    ],
)
@pytest.mark.parametrize(
    "tail,kind", [("Ext/Module.bsl", "bsl"), ("Ext/Help.xml", "resource")]
)
def test_owner_binding_requires_designer_namespace_on_root_and_object(
    root_ns, node_ns, reason, tail, kind
):
    tree = {
        "CommonModules/Item.xml": metadata(
            "CommonModule", "Item", root_ns=root_ns, node_ns=node_ns
        ),
        "CommonModules/Item/" + tail: b"<Help>PRIVATE</Help>",
    }
    row = scopes(tree)[0]
    assert row["kind"] == kind
    assert row["object_uuid"] == UUID
    if reason is None and kind == "bsl":
        assert row["status"] == "supported"
        assert materialize_metadata_three_way(tree, tree, tree)["candidate"] == tree
        return
    expected = reason or "resource_kind_unsupported"
    assert row["status"] == "unsupported"
    assert row["reason"] == expected
    assert expected in reasons(blocked(tree))


@pytest.mark.parametrize(
    "raw",
    [
        f'<MetaDataObject xmlns="{MD_NS}"/>',
        f'<MetaDataObject xmlns="{MD_NS}"><Catalog><Properties><Name>Products'
        "</Name></Properties></Catalog></MetaDataObject>",
        f'<MetaDataObject xmlns="{MD_NS}"><Catalog uuid="{UUID}"><Properties>'
        f'<Name>Products</Name></Properties></Catalog><Document uuid="{OTHER_UUID}">'
        "<Properties><Name>Other</Name></Properties></Document></MetaDataObject>",
    ],
    ids=["no_object", "no_uuid", "two_objects"],
)
def test_unknown_object_descriptor_shape_blocks_even_when_unchanged(raw):
    tree = {OWNER: raw.encode()}
    result = plan(tree)
    assert result["objects"] == []
    assert result["unsupported_files"] == [OWNER]
    error = blocked(tree)
    assert reasons(error) == {"object_shape_unsupported"}
    assert error.details["blocking_scope_count"] == 3


@pytest.mark.parametrize("other_kind", ["Catalog", "Document"])
@pytest.mark.parametrize("spelling", [str.lower, str.upper])
def test_one_uuid_names_one_descriptor_per_snapshot_whatever_its_type(
    other_kind, spelling
):
    tree = {
        OWNER: metadata(),
        "Documents/Other.xml": metadata(other_kind, "Other", identity=spelling(UUID)),
    }
    for function in (plan_metadata_three_way, materialize_metadata_three_way):
        with pytest.raises(CoreError) as caught:
            function(tree, tree, tree)
        assert caught.value.code == "THREE_WAY_METADATA_INVALID"
        assert "PRIVATE" not in json.dumps(caught.value.to_dict("request"))


def test_uuid_spelling_does_not_split_one_identity():
    base = {OWNER: metadata(identity=UUID.upper())}
    current = {OWNER: metadata(identity=UUID, name="Local")}
    result = plan(base, current, base)
    assert [(row["object_uuid"], row["action"]) for row in result["objects"]] == [
        (UUID, "keep_current")
    ]


def test_uuid_bound_to_another_object_type_across_snapshots_blocks():
    base = {OWNER: metadata()}
    current = {"Documents/Products.xml": metadata("Document")}

    rows = plan(base, current, base)["objects"]
    assert [(row["object_type"], row["object_uuid"]) for row in rows] == [
        ("Catalog", UUID),
        ("Document", UUID),
    ]
    error = blocked(base, current, base)
    assert error.details["blocking_scopes"] == [
        {"object_uuid": UUID, "reason": "object_type_changed"}
    ]


def test_replacing_uuid_at_a_reused_descriptor_path_blocks():
    base = {OWNER: metadata()}
    current = {OWNER: metadata(identity=OTHER_UUID)}
    assert reasons(blocked(base, current, base)) == {"object_identity_changed"}
