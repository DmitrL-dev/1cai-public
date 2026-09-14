"""A selected synthetic EDT Catalog projection never authorizes a merge."""

from collections.abc import Mapping
import copy
import hashlib
import json
from pathlib import Path

import pytest

import rentgen_core as api


FIXTURE = Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-inventory-v1"
PATH = "Catalogs/Products/Products.mdo"
NS = "http://g5.1c.ru/v8/dt/metadata/mdclass"
OWNER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CHILD = "10000000-0000-4000-8000-000000000020"
OTHER = "99999999-9999-4999-8999-999999999999"


@pytest.fixture
def tree():
    return {PATH: (FIXTURE / "base" / PATH).read_bytes()}


def plan(*trees, **limits):
    assert hasattr(api, "plan_edt_attribute_three_way"), "EDT child planner is absent"
    return api.plan_edt_attribute_three_way(*trees, **limits)


def edited(tree, old, new):
    return {path: raw.replace(old, new) for path, raw in tree.items()}


def attribute(raw):
    return raw[raw.index(b"<attributes ") : raw.index(b"</attributes>") + 13]


def rejected(trees, reason, **limits):
    before = copy.deepcopy(trees)
    with pytest.raises(api.CoreError) as caught:
        plan(*trees, **limits)
    assert caught.value.details["reason"] == reason
    assert "SECRET" not in json.dumps(caught.value.to_dict("request"))
    assert "child_objects" not in caught.value.details
    assert trees == before


def test_fixture_identity_and_exact_source_evidence(tree):
    result = plan(tree, tree, tree)
    assert result["scope"] == "edt-catalog-attributes-v1"
    assert result["mode"] == "read_only"
    assert result["coverage"] == "partial"
    assert len(result["child_objects"]) == 1
    row = result["child_objects"][0]
    assert (row["child_type"], row["child_uuid"], row["action"]) == (
        "Attribute",
        CHILD,
        "unchanged",
    )
    assert row["property_changes"] == []
    for label in ("base", "current", "upstream"):
        value = row[label]
        assert value["name"] == "Article"
        assert value["owner"] == {"type": "Catalog", "uuid": OWNER, "path": PATH}
        assert value["xml_path"] == "/Catalog/attributes[1]"
        assert value["source_sha256"] == hashlib.sha256(tree[PATH]).hexdigest()
        assert value["source_size_bytes"] == len(tree[PATH])
        assert value["size_bytes"] > 0
        assert len(value["sha256"]) == 64


def test_child_rename_and_owner_rename_preserve_uuid(tree):
    current = edited(tree, b"Article", b"SKU")
    upstream = {"Catalogs/Items/Items.mdo": tree[PATH].replace(b"Products", b"Items")}
    row = plan(tree, current, upstream)["child_objects"][0]
    assert row["child_uuid"] == CHILD
    assert row["current"]["name"] == "SKU"
    assert row["upstream"]["owner"]["uuid"] == OWNER
    assert row["upstream"]["owner"]["path"] == "Catalogs/Items/Items.mdo"
    assert row["property_changes"][0]["property_name"] == "name"
    assert row["property_changes"][0]["action"] == "keep_current"


def test_disjoint_direct_properties_are_evidence_only(tree):
    base = edited(tree, b"</attributes>", b"<comment>old</comment></attributes>")
    current = edited(base, b"Article", b"SKU")
    upstream = edited(base, b">old<", b">SECRET new<")
    result = plan(base, current, upstream)
    row = result["child_objects"][0]
    assert row["action"] == "conflict"
    assert row["property_mergeability"] == "disjoint_changes"
    assert [(r["property_name"], r["action"]) for r in row["property_changes"]] == [
        ("comment", "take_upstream"),
        ("name", "keep_current"),
    ]
    assert "SECRET" not in json.dumps(result)
    assert "candidate" not in result


@pytest.mark.parametrize(
    "case,action,mergeability",
    [
        ("same", "same_change", "same_change"),
        ("overlap", "conflict", "overlap_conflict"),
        ("add", "take_upstream", "not_available"),
        ("delete", "keep_current", "not_available"),
        ("delete_modify", "conflict", "not_available"),
    ],
)
def test_child_actions(tree, case, action, mergeability):
    removed = edited(tree, attribute(tree[PATH]), b"")
    changed = edited(tree, b"Article", b"SKU")
    values = {
        "same": (tree, changed, changed),
        "overlap": (tree, changed, edited(tree, b"Article", b"OtherName")),
        "add": (removed, removed, tree),
        "delete": (tree, removed, tree),
        "delete_modify": (tree, removed, changed),
    }[case]
    row = plan(*values)["child_objects"][0]
    assert (row["action"], row["property_mergeability"]) == (action, mergeability)
    assert (row["base"] is None) == (case == "add")
    assert (row["current"] is None) == (case in {"add", "delete", "delete_modify"})


def test_direct_property_addition_and_deletion_are_classified(tree):
    base = edited(tree, b"</attributes>", b"<comment>old</comment></attributes>")
    current = tree
    upstream = edited(
        base, b"</attributes>", b"<indexing>Index</indexing></attributes>"
    )
    row = plan(base, current, upstream)["child_objects"][0]
    assert row["property_mergeability"] == "disjoint_changes"
    values = {p["property_name"]: p for p in row["property_changes"]}
    assert values["comment"]["current_sha256"] is None
    assert values["indexing"]["base_sha256"] is None


@pytest.mark.parametrize(
    "old,new,reason",
    [
        (NS.encode(), b"urn:SECRET", "namespace_unsupported"),
        (OWNER.encode(), b"invalidSECRET", "identity_invalid"),
        (CHILD.encode(), b"invalidSECRET", "identity_invalid"),
        (OWNER.encode(), b"00000000-0000-0000-0000-000000000000", "identity_invalid"),
        (
            b"<name>Article</name>",
            b"<name>Article</name><name>SECRET</name>",
            "property_ambiguous",
        ),
        (b"<name>Article</name>", b"", "identity_invalid"),
        (b"<attributes ", b'<attributes xmlns="urn:SECRET" ', "namespace_unsupported"),
        (
            b"<name>Article</name>",
            b'<name xmlns="urn:SECRET">Article</name>',
            "namespace_unsupported",
        ),
        (
            b"<name>Article</name>",
            b"<name><part>SECRET</part></name>",
            "identity_invalid",
        ),
        (
            b"</attributes>",
            b'<nested uuid="99999999-9999-4999-8999-999999999999"/></attributes>',
            "nested_identity_unsupported",
        ),
        (b"</attributes>", b"SECRET</attributes>", "mixed_content_unsupported"),
    ],
)
def test_malformed_selected_input_fails_without_partial_evidence(
    tree, old, new, reason
):
    bad = edited(tree, old, new)
    rejected((tree, tree, bad), reason)


@pytest.mark.parametrize("case", ["same_uuid", "same_name", "owner_uuid"])
def test_duplicate_children_fail_closed(tree, case):
    raw = attribute(tree[PATH])
    if case == "same_name":
        raw = raw.replace(CHILD.encode(), OTHER.encode()).replace(
            b"Article", b"ARTICLE"
        )
    elif case == "owner_uuid":
        raw = raw.replace(CHILD.encode(), OWNER.encode()).replace(b"Article", b"Other")
    bad = edited(tree, b"</md:Catalog>", raw + b"</md:Catalog>")
    rejected((tree, bad, tree), "identity_duplicate")


def test_owner_transfer_fails_even_when_attribute_bytes_do_not_change(tree):
    other = {
        "Catalogs/Other/Other.mdo": tree[PATH]
        .replace(b"Products", b"Other")
        .replace(OWNER.encode(), OTHER.encode())
    }
    rejected((tree, other, tree), "owner_changed")


def test_missing_owner_version_is_not_attribute_deletion_authority(tree):
    rejected((tree, {}, tree), "owner_missing")


def test_replacing_owner_at_same_path_fails_closed(tree):
    rejected(
        (tree, edited(tree, OWNER.encode(), OTHER.encode()), tree),
        "owner_identity_changed",
    )


def test_unknown_extension_fixture_is_rejected(tree):
    bad = {PATH: (FIXTURE / "negative/unknown-extension.mdo").read_bytes()}
    rejected((tree, tree, bad), "identity_shape_unsupported")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_forbidden_declarations_never_expand(tree, encoding):
    text = '<!DOCTYPE Catalog [<!ENTITY x "SECRET">]>' + tree[PATH].decode()
    rejected((tree, {PATH: text.encode(encoding)}, tree), "xml_declaration_forbidden")


@pytest.mark.parametrize(
    "option,value",
    [("max_children", 0), ("max_children", True), ("max_children", 20001)],
)
def test_child_limits_are_bounded_integers(tree, option, value):
    rejected((tree, tree, tree), "limits_invalid", **{option: value})


def test_child_union_limit_is_independent_of_file_count(tree):
    one = edited(tree, CHILD.encode(), OTHER.encode())
    rejected((tree, one, tree), "child_limit", max_children=1)


def test_paths_must_be_selected_catalog_descriptors(tree):
    rejected((tree, {"Other.mdo": tree[PATH]}, tree), "path_unsupported")


def test_reordered_inputs_do_not_change_evidence_or_touch_io(tree, monkeypatch):
    before = copy.deepcopy(tree)
    expected = plan(tree, tree, tree)

    def forbidden(*args, **kwargs):
        pytest.fail("Pure evidence must not access files or processes")

    with monkeypatch.context() as patch:
        patch.setattr("builtins.open", forbidden)
        patch.setattr("os.open", forbidden)
        patch.setattr("subprocess.Popen", forbidden)
        assert plan(tree, tree, tree) == expected
    assert tree == before


def test_each_caller_mapping_is_captured_once(tree):
    class Once(Mapping):
        reads = 0

        def __iter__(self):
            return iter(tree)

        def __len__(self):
            return len(tree)

        def __getitem__(self, key):
            pytest.fail("No original mapping reread")

        def items(self):
            self.reads += 1
            assert self.reads == 1
            return tree.items()

    assert len(plan(Once(), Once(), Once())["child_objects"]) == 1


def test_divergent_owner_renames_are_not_unchanged_evidence(tree):
    def moved(name):
        return {
            f"Catalogs/{name}/{name}.mdo": tree[PATH].replace(
                b"Products", name.encode()
            )
        }

    rejected((tree, moved("Ours"), moved("Theirs")), "owner_path_conflict")


def test_same_names_under_distinct_owners_and_mapping_order(tree):
    other = (
        tree[PATH]
        .replace(b"Products", b"Other")
        .replace(OWNER.encode(), OTHER.encode())
        .replace(b"10000000-", b"20000000-")
    )
    together = {**tree, "Catalogs/Other/Other.mdo": other}
    before = copy.deepcopy(together)
    result = plan(together, together, together)
    reverse = dict(reversed(tuple(together.items())))
    assert plan(reverse, reverse, reverse) == result
    assert len(result["child_objects"]) == 2
    assert together == before


def test_duplicate_uuid_between_catalogs_is_rejected(tree):
    other = (
        tree[PATH]
        .replace(b"Products", b"Other")
        .replace(OWNER.encode(), OTHER.encode())
    )
    bad = {**tree, "Catalogs/Other/Other.mdo": other}
    rejected((tree, bad, tree), "identity_duplicate")


def test_property_limit_and_xml_depth_are_bounded(tree):
    properties = b"".join(
        f"<field{index}/ >".replace("/ >", "/>").encode() for index in range(128)
    )
    rejected(
        (tree, edited(tree, b"</attributes>", properties + b"</attributes>"), tree),
        "property_limit",
    )
    deep = b"<value>" * 65 + b"SECRET" + b"</value>" * 65
    rejected(
        (tree, edited(tree, b"</attributes>", deep + b"</attributes>"), tree),
        "xml_limit",
    )


@pytest.mark.parametrize("case", ["bytes", "files", "path", "malformed", "name_path"])
def test_invalid_inputs_fail_without_payload(tree, case):
    if case == "bytes":
        with pytest.raises(api.CoreError, match="byte limit"):
            plan(tree, tree, tree, max_file_bytes=1)
    elif case == "files":
        other = {"Catalogs/Other/Other.mdo": b"SECRET"}
        with pytest.raises(api.CoreError, match="file limit"):
            plan(tree, other, tree, max_files=1)
    elif case == "path":
        with pytest.raises(api.CoreError, match="paths"):
            plan(tree, {"../SECRET.mdo": b"SECRET"}, tree)
    elif case == "malformed":
        rejected((tree, {PATH: b"<SECRET"}, tree), "xml_invalid")
    else:
        rejected(
            (tree, edited(tree, b"Products", b"Other"), tree), "path_name_mismatch"
        )


def test_empty_selected_trees_produce_empty_read_only_evidence():
    result = plan({}, {}, {})
    assert result["child_objects"] == []
    assert result["mode"] == "read_only"


def test_uppercase_uuid_keeps_identity_and_marks_unscoped_change(tree):
    # Hex letters make the same UUID's observed spelling change.
    base = edited(tree, CHILD.encode(), b"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    current = edited(
        base,
        b"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        b"AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
    )
    row = plan(base, current, base)["child_objects"][0]
    assert row["child_uuid"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert row["action"] == "keep_current"
    assert row["property_mergeability"] == "unscoped_content"


def test_xml_comments_are_not_reported_as_supported_unchanged(tree):
    bad = edited(tree, b"</attributes>", b"<!--SECRET--></attributes>")
    rejected((tree, bad, tree), "xml_misc_unsupported")


def test_namespace_binding_changes_cannot_hide_behind_identical_qname_text(tree):
    base = edited(tree, b"<md:Catalog ", b'<md:Catalog xmlns:cfg="urn:first" ')
    base = edited(
        base, b"</attributes>", b"<valueType>cfg:Item</valueType></attributes>"
    )
    current = edited(base, b"urn:first", b"urn:second")
    row = plan(base, current, base)["child_objects"][0]
    assert row["action"] == "keep_current"
    assert row["base"]["sha256"] != row["current"]["sha256"]


def test_unknown_xml_encoding_returns_a_structured_error(tree):
    bad = {PATH: b'<?xml version="1.0" encoding="SECRET-UNKNOWN"?>' + tree[PATH]}
    rejected((tree, bad, tree), "xml_invalid")
