"""Qualified in-memory Designer property merges never expose partial trees."""

from collections.abc import Mapping
import xml.etree.ElementTree as ET

import pytest

import rentgen_core.metadata_three_way as metadata_merge
from rentgen_core.errors import CoreError
from rentgen_core.three_way import plan_three_way


NS = "http://v8.1c.ru/8.3/MDClasses"
UUID = "11111111-1111-4111-8111-111111111111"
OTHER_UUID = "22222222-2222-4222-8222-222222222222"
PATH = "Catalogs/Products.xml"


def xml(properties="", *, name="Products", identity=UUID, extra="", wrapper=""):
    return (
        f'<MetaDataObject xmlns="{NS}" xmlns:v8="urn:types" {wrapper}>'
        f'<Catalog uuid="{identity}"><Properties><Name>{name}</Name>'
        f"{properties}</Properties><ChildObjects/>{extra}</Catalog></MetaDataObject>"
    ).encode()


def materialize(*trees, **kwargs):
    function = getattr(metadata_merge, "materialize_metadata_three_way", None)
    assert callable(function), "The qualified metadata materializer is not implemented"
    return function(*trees, **kwargs)


def properties(raw):
    node = ET.fromstring(raw).find(f"{{{NS}}}Catalog/{{{NS}}}Properties")
    return {child.tag.rsplit("}", 1)[-1]: child.text for child in node}


def test_merges_disjoint_properties_and_preserves_qname_namespace_bytes():
    base = {PATH: xml("<Code>CAT</Code><Type>v8:String</Type><Shared>0</Shared>")}
    current = {
        PATH: xml(
            "<Code>CAT</Code><Type>v8:String</Type><Shared>1</Shared>", name="Local"
        )
    }
    upstream = {PATH: xml("<Code>ITEM</Code><Type>v8:String</Type><Shared>1</Shared>")}
    originals = tuple(tree.copy() for tree in (base, current, upstream))

    result = materialize(base, current, upstream)

    assert result["schema"] == 1
    assert result["scope"] == "metadata-properties-v1"
    assert result["status"] == "ready"
    assert properties(result["candidate"][PATH]) == {
        "Name": "Local",
        "Code": "ITEM",
        "Type": "v8:String",
        "Shared": "1",
    }
    assert b'xmlns:v8="urn:types"' in result["candidate"][PATH]
    assert (base, current, upstream) == originals
    for label, tree in zip(
        ("base", "current", "upstream", "candidate"), (*originals, result["candidate"])
    ):
        assert (
            result[label + "_digest"] == plan_three_way(tree, tree, tree)["base_digest"]
        )
    assert result["counts"]["merged_objects"] == 1
    assert result["merged_objects"][0]["object_uuid"] == UUID
    assert result["merged_objects"][0]["candidate_path"] == PATH


def test_merges_property_addition_and_deletion_with_a_uuid_bound_move():
    base = {PATH: xml("<Code>CAT</Code><Delete>old</Delete>")}
    moved = "Catalogs/Renamed.xml"
    current = {moved: xml("<Code>CAT</Code>", name="Local")}
    upstream = {PATH: xml("<Added>new</Added><Code>ITEM</Code><Delete>old</Delete>")}
    result = materialize(base, current, upstream)
    assert set(result["candidate"]) == {moved}
    assert properties(result["candidate"][moved]) == {
        "Name": "Local",
        "Added": "new",
        "Code": "ITEM",
    }
    assert list(properties(result["candidate"][moved])) == ["Name", "Added", "Code"]


def test_atomic_paths_preserve_additions_deletions_and_supported_companions():
    module = "Catalogs/Products/Ext/ObjectModule.bsl"
    base = {PATH: xml(), module: b"base", "removed.txt": b"remove", "same.txt": b"old"}
    current = {
        PATH: xml(name="Local"),
        module: b"base",
        "same.txt": b"same",
        "local.txt": b"local",
    }
    upstream = {
        PATH: xml(),
        module: b"upstream",
        "removed.txt": b"remove",
        "same.txt": b"same",
        "remote.txt": b"remote",
    }
    result = materialize(base, current, upstream)
    assert result["candidate"] == {
        PATH: current[PATH],
        module: b"upstream",
        "same.txt": b"same",
        "local.txt": b"local",
        "remote.txt": b"remote",
    }
    assert result["counts"]["merged_objects"] == 0


@pytest.mark.parametrize(
    "function_name", ["plan_metadata_three_way", "materialize_metadata_three_way"]
)
def test_metadata_uses_one_captured_mapping_snapshot(function_name):
    class DriftingMapping(Mapping):
        def __init__(self):
            self.reads = 0

        def __getitem__(self, key):
            raise AssertionError("Original mapping was read after capture")

        def __iter__(self):
            return iter([PATH])

        def __len__(self):
            return 1

        def items(self):
            self.reads += 1
            assert self.reads == 1, "Original mapping was read after capture"
            return {PATH: xml()}.items()

    tree = DriftingMapping()
    function = getattr(metadata_merge, function_name, None)
    assert callable(function)
    result = function({PATH: xml()}, tree, {PATH: xml()})
    assert result["current_digest"] == result["base_digest"]
    if "candidate" in result:
        assert result["candidate"] == {PATH: xml()}


@pytest.mark.parametrize(
    "bad",
    [
        "overlap",
        "unscoped",
        "wrapper",
        "properties_attribute",
        "foreign_namespace",
        "missing_properties",
        "duplicate_properties",
        "extension",
        "divergent_move",
        "owner_replaced",
    ],
)
def test_unsupported_or_conflicting_objects_fail_closed(bad):
    base = {PATH: xml("<Code>CAT</Code>")}
    current = {PATH: xml("<Code>CAT</Code>", name="Local")}
    upstream = {PATH: xml("<Code>ITEM</Code>")}
    if bad == "overlap":
        upstream[PATH] = xml("<Code>CAT</Code>", name="Remote")
    elif bad == "unscoped":
        upstream[PATH] = xml("<Code>ITEM</Code>", extra="<Unknown>private</Unknown>")
    elif bad == "wrapper":
        upstream[PATH] = xml("<Code>ITEM</Code>", wrapper='version="2"')
    elif bad == "properties_attribute":
        upstream[PATH] = upstream[PATH].replace(
            b"<Properties>", b'<Properties marker="private">'
        )
    elif bad == "foreign_namespace":
        for tree in (base, current, upstream):
            tree[PATH] = tree[PATH].replace(NS.encode(), b"urn:foreign")
    elif bad == "missing_properties":
        upstream[PATH] = (
            upstream[PATH]
            .replace(b"<Properties>", b"<Unknown>")
            .replace(b"</Properties>", b"</Unknown>")
        )
    elif bad == "duplicate_properties":
        upstream[PATH] = upstream[PATH].replace(
            b"</Properties>",
            b"</Properties><Properties><Code>extra</Code></Properties>",
        )
    elif bad == "extension":
        for tree in (base, current, upstream):
            tree[PATH] = tree[PATH].replace(
                b"</Properties>", b"<ObjectBelonging>Own</ObjectBelonging></Properties>"
            )
    elif bad == "divergent_move":
        current["Catalogs/Local.xml"] = current.pop(PATH)
        upstream["Catalogs/Remote.xml"] = upstream.pop(PATH)
    elif bad == "owner_replaced":
        upstream[PATH] = upstream[PATH].replace(UUID.encode(), OTHER_UUID.encode())
    with pytest.raises(CoreError) as error:
        materialize(base, current, upstream)
    assert "candidate" not in error.value.details
    assert "private" not in str(error.value.details)
    assert "<" not in str(error.value.details)


@pytest.mark.parametrize("scope", ["unsupported", "conflict", "owner_move"])
def test_companion_scopes_cannot_be_bypassed_by_property_merge(scope):
    module = "Catalogs/Products/Ext/ObjectModule.bsl"
    base = {PATH: xml("<Code>CAT</Code>"), module: b"private base"}
    current = {PATH: xml("<Code>CAT</Code>", name="Local"), module: b"private local"}
    upstream = {PATH: xml("<Code>ITEM</Code>"), module: b"private remote"}
    if scope == "unsupported":
        for tree in (base, current, upstream):
            tree["Catalogs/Products/Ext/Unknown.bsl"] = tree.pop(module)
    elif scope == "owner_move":
        current["Catalogs/Moved.xml"] = current.pop(PATH)
    with pytest.raises(CoreError) as error:
        materialize(base, current, upstream)
    assert "private" not in str(error.value.details)
    assert "candidate" not in error.value.details


def test_conflict_details_are_bounded():
    base = {f"files/{index}.txt": b"private base" for index in range(300)}
    current = {path: b"private local" for path in base}
    upstream = {path: b"private remote" for path in base}
    with pytest.raises(CoreError) as error:
        materialize(base, current, upstream)
    assert error.value.code == "THREE_WAY_CONFLICT"
    assert len(error.value.details["blocking_scopes"]) == 256
    assert error.value.details["blocking_scope_count"] == 300
    assert error.value.details["scopes_truncated"] is True
    assert "private" not in str(error.value.details)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_forbidden_declarations_are_rejected_before_merge(encoding):
    raw = ('<!DOCTYPE MetaDataObject [<!ENTITY x "private">]>' + xml().decode()).encode(
        encoding
    )
    with pytest.raises(CoreError, match="DTD|ENTITY"):
        materialize({PATH: raw}, {PATH: raw}, {PATH: raw})


def test_empty_direct_properties_and_prefixed_metadata_preserve_valid_xml():
    def prefixed(raw):
        root = raw.replace(b"<MetaDataObject xmlns=", b"<m:MetaDataObject xmlns:m=")
        for tag in ("Catalog", "Properties", "Name", "Code", "Empty", "ChildObjects"):
            root = root.replace(("<" + tag).encode(), ("<m:" + tag).encode())
            root = root.replace(("</" + tag).encode(), ("</m:" + tag).encode())
        return root.replace(b"</MetaDataObject>", b"</m:MetaDataObject>")

    base = {PATH: prefixed(xml("<Code>CAT</Code><Empty/>"))}
    current = {PATH: prefixed(xml("<Code>CAT</Code><Empty/>", name="Местный"))}
    upstream = {PATH: prefixed(xml("<Code>ITEM</Code><Empty/>"))}
    result = materialize(base, current, upstream)
    assert properties(result["candidate"][PATH]) == {
        "Name": "Местный",
        "Code": "ITEM",
        "Empty": None,
    }
    assert b"<m:Empty/>" in result["candidate"][PATH]


def test_candidate_combined_growth_is_checked_against_limits():
    base = {PATH: xml("<Left/><Right/>")}
    current = {PATH: xml("<Left>" + "a" * 100 + "</Left><Right/>")}
    upstream = {PATH: xml("<Left/><Right>" + "b" * 100 + "</Right>")}
    with pytest.raises(CoreError) as error:
        materialize(
            base,
            current,
            upstream,
            max_file_bytes=max(len(current[PATH]), len(upstream[PATH])),
        )
    assert error.value.code == "THREE_WAY_LIMIT"
    assert "candidate" not in error.value.details


@pytest.mark.parametrize(
    "change",
    ["comment", "property_order", "mixed_text", "qname_context", "foreign_property"],
)
def test_unqualified_property_layout_changes_are_not_silently_lost(change):
    base = {PATH: xml("<Left>0</Left><Right>0</Right>")}
    current = {PATH: xml("<Left>1</Left><Right>0</Right>")}
    upstream = {PATH: xml("<Left>0</Left><Right>1</Right>")}
    if change == "comment":
        upstream[PATH] = upstream[PATH].replace(b"</Name>", b"<!--private--></Name>")
    elif change == "property_order":
        upstream[PATH] = xml("<Right>1</Right><Left>0</Left>")
    elif change == "mixed_text":
        upstream[PATH] = upstream[PATH].replace(
            b"</Properties>", b"private</Properties>"
        )
    elif change == "qname_context":
        upstream[PATH] = upstream[PATH].replace(
            b'xmlns:v8="urn:types"', b'xmlns:v8="urn:other"'
        )
    else:
        for tree in (base, current, upstream):
            tree[PATH] = tree[PATH].replace(b"<Left>", b'<Left xmlns="urn:foreign">')
    with pytest.raises(CoreError) as error:
        materialize(base, current, upstream)
    assert "private" not in str(error.value.details)


def test_atomic_one_sided_object_keeps_unscoped_bytes_verbatim():
    base = {PATH: xml()}
    current = {PATH: xml(extra="<Unknown><Inner/></Unknown>")}
    result = materialize(base, current, base)
    assert result["candidate"][PATH] is current[PATH]
    assert result["merged_objects"] == []


def test_materialized_object_evidence_is_bounded_and_deterministic():
    trees = [{}, {}, {}]
    for index in range(257):
        identity = f"{index:08x}-1111-4111-8111-111111111111"
        path = f"Catalogs/Item{index}.xml"
        for tree, name, code in zip(trees, ("Base", "Local", "Base"), ("0", "0", "1")):
            tree[path] = xml(f"<Code>{code}</Code>", name=name, identity=identity)
    result = materialize(*trees)
    assert result["counts"]["merged_objects"] == 257
    assert len(result["merged_objects"]) == 256
    assert result["merged_objects_truncated"] is True
    assert result == materialize(
        *(dict(reversed(tuple(tree.items()))) for tree in trees)
    )


@pytest.mark.parametrize("encoding", ["utf-16", "iso-8859-1"])
def test_non_utf8_property_splicing_fails_closed(encoding):
    trees = [
        {PATH: xml("<Code>0</Code>")},
        {PATH: xml("<Code>0</Code>", name="Local")},
        {PATH: xml("<Code>1</Code>")},
    ]
    for tree in trees:
        tree[PATH] = (
            f'<?xml version="1.0" encoding="{encoding}"?>' + tree[PATH].decode()
        ).encode(encoding)
    with pytest.raises(CoreError):
        materialize(*trees)


def test_merge_preserves_property_spacing_and_xml_space_context():
    def formatted(name, code):
        return (
            xml(f"<Code>{code}</Code>", name=name)
            .replace(b"<Properties>", b'<Properties xml:space="preserve">\n  ')
            .replace(b"</Name>", b"</Name>\n  ")
            .replace(b"</Code>", b"</Code>\n")
        )

    base = {PATH: formatted("Base", "0")}
    current = {PATH: formatted("Local", "0")}
    upstream = {PATH: formatted("Base", "1")}
    assert materialize(base, current, upstream)["candidate"][PATH] == formatted(
        "Local", "1"
    )


@pytest.mark.parametrize(
    "scope,root",
    [
        ("Ext/Form.xml", '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform"/>'),
        ("ext/form.xml", '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform"/>'),
        ("eXt/FoRm.XML", '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform"/>'),
        (
            "Ext/Template.xml",
            '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"/>',
        ),
        (
            "ext/template.xml",
            '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"/>',
        ),
        (
            "EXT/TEMPLATE.XML",
            '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"/>',
        ),
    ],
)
@pytest.mark.parametrize("prefix", ["Orphan/Item/", ""])
def test_orphan_xml_companion_casing_cannot_bypass_semantic_gate(scope, root, prefix):
    path = prefix + scope
    tree = {path: root.encode()}
    with pytest.raises(CoreError) as error:
        materialize(tree, tree, tree)
    assert any(
        row["reason"] == "owner_not_found"
        for row in error.value.details["blocking_scopes"]
    )
