"""Semantic evidence is atomic, UUID-bound, deterministic and read-only."""

import copy
import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.metadata_three_way import plan_metadata_three_way


UUID = "11111111-1111-4111-8111-111111111111"
OTHER_UUID = "22222222-2222-4222-8222-222222222222"
MD_NS = "http://v8.1c.ru/8.3/MDClasses"
FORM_NS = "http://v8.1c.ru/8.3/xcf/logform"
DCS_NS = "http://v8.1c.ru/8.1/data-composition-system/schema"


def metadata(kind, name="Item", *, identity=UUID, properties="", children=""):
    return (
        f'<MetaDataObject xmlns="{MD_NS}"><{kind} uuid="{identity}">'
        f"<Properties><Name>{name}</Name>{properties}</Properties>"
        f"<ChildObjects>{children}</ChildObjects></{kind}></MetaDataObject>"
    ).encode()


def semantic_rows(base, current=None, upstream=None):
    return plan_metadata_three_way(
        base,
        base if current is None else current,
        base if upstream is None else upstream,
    )["semantics"]["scopes"]


@pytest.mark.parametrize(
    "kind,path,tail,raw,scope_kind",
    [
        ("CommonModule", "CommonModules/Item", "Module.bsl", b"Return 1;", "bsl"),
        (
            "Form",
            "Catalogs/Products/Forms/Item",
            "Form.xml",
            f'<Form xmlns="{FORM_NS}"><AutoTitle>true</AutoTitle></Form>'.encode(),
            "form",
        ),
        (
            "Form",
            "Catalogs/Products/Forms/Item",
            "Form/Module.bsl",
            b"Return 1;",
            "bsl",
        ),
        (
            "Template",
            "Reports/Report/Templates/Item",
            "Template.xml",
            f'<DataCompositionSchema xmlns="{DCS_NS}"/>'.encode(),
            "data_composition_schema",
        ),
    ],
)
def test_supported_companions_are_bound_to_exact_uuid_owner(
    kind, path, tail, raw, scope_kind
):
    props = (
        "<TemplateType>DataCompositionSchema</TemplateType>"
        if kind == "Template"
        else ""
    )
    tree = {
        path + ".xml": metadata(kind, properties=props),
        path + "/Ext/" + tail: raw,
    }
    row = semantic_rows(tree)[0]
    assert row["object_uuid"] == UUID
    assert row["object_type"] == kind
    assert row["kind"] == scope_kind
    assert row["scope"] == "Ext/" + tail
    assert row["status"] == "supported"
    assert row["granularity"] == "atomic_bytes"
    assert row["action"] == "unchanged"
    assert row["base_path"] == path + "/Ext/" + tail


def test_module_follows_uuid_rename_and_conflicting_bytes_stay_conflict():
    def tree(name, raw):
        return {
            f"CommonModules/{name}.xml": metadata("CommonModule", name),
            f"CommonModules/{name}/Ext/Module.bsl": raw,
        }

    base = tree("Base", b"Return 0;")
    current = tree("Local", b"Return 1;")
    upstream = tree("Remote", b"Return 2;")
    row = semantic_rows(base, current, upstream)[0]
    assert row["object_uuid"] == UUID
    assert row["status"] == "conflict"
    assert row["action"] == "conflict"
    assert row["current_path"] == "CommonModules/Local/Ext/Module.bsl"
    assert row["upstream_path"] == "CommonModules/Remote/Ext/Module.bsl"


@pytest.mark.parametrize(
    "current,upstream,action",
    [
        (b"one", b"base", "keep_current"),
        (b"base", b"two", "take_upstream"),
        (b"same", b"same", "same_change"),
        (None, b"edited", "conflict"),
    ],
)
def test_atomic_module_actions_include_delete_modify(current, upstream, action):
    def tree(raw):
        result = {"CommonModules/Item.xml": metadata("CommonModule")}
        if raw is not None:
            result["CommonModules/Item/Ext/Module.bsl"] = raw
        return result

    row = semantic_rows(tree(b"base"), tree(current), tree(upstream))[0]
    assert row["action"] == action
    assert row["status"] == ("conflict" if action == "conflict" else "supported")


@pytest.mark.parametrize(
    "tree,reason",
    [
        ({"CommonModules/Item/Ext/Module.bsl": b"Return 1;"}, "owner_not_found"),
        (
            {
                "Catalogs/Item.xml": metadata("Catalog"),
                "Catalogs/Item/Ext/Module.bsl": b"Return 1;",
            },
            "owner_type_unsupported",
        ),
        (
            {
                "CommonModules/Item.xml": metadata("CommonModule"),
                "CommonModules/Item/Ext/Module.bsl": b"\xff",
            },
            "bsl_encoding_unsupported",
        ),
        (
            {
                "CommonForms/Item.xml": metadata("CommonForm"),
                "CommonForms/Item/Ext/Form.xml": b'<Form xmlns="urn:unknown"/>',
            },
            "xml_shape_unsupported",
        ),
        (
            {
                "Templates/Item.xml": metadata("Template"),
                "Templates/Item/Ext/Template.xml": f'<DataCompositionSchema xmlns="{DCS_NS}"/>'.encode(),
            },
            "template_type_unsupported",
        ),
        (
            {
                "CommonModules/Item.xml": metadata("CommonModule"),
                "CommonModules/Item/Ext/Unknown.bsl": b"Return 1;",
            },
            "scope_unsupported",
        ),
    ],
)
def test_unsupported_companions_have_explicit_reason(tree, reason):
    row = semantic_rows(tree)[0]
    assert row["status"] == "unsupported"
    assert row["reason"] == reason


def test_companion_cannot_fall_back_to_parent_uuid_for_missing_nested_form():
    tree = {
        "Catalogs/Item.xml": metadata("Catalog"),
        "Catalogs/Item/Forms/Missing/Ext/Form/Module.bsl": b"Return 1;",
    }
    row = semantic_rows(tree)[0]
    assert row["status"] == "unsupported"
    assert row["object_uuid"] is None
    assert row["reason"] == "owner_not_found"


def test_extension_declarations_do_not_claim_verified_base_configuration_ownership():
    base = {
        "Catalogs/Item.xml": metadata(
            "Catalog", properties="<ObjectBelonging>Adopted</ObjectBelonging>"
        )
    }
    current = {
        "Catalogs/Item.xml": metadata(
            "Catalog", properties="<ObjectBelonging>Own</ObjectBelonging>"
        )
    }
    row = semantic_rows(base, current, base)[0]
    assert row["kind"] == "extension"
    assert row["object_uuid"] == UUID
    assert row["action"] == "keep_current"
    assert row["status"] == "unsupported"
    assert row["reason"] == "extension_ownership_unverified"


def test_name_is_direct_property_and_nested_child_names_are_not_ambiguous():
    tree = {
        "Catalogs/Item.xml": metadata(
            "Catalog",
            children=(
                f'<Attribute uuid="{OTHER_UUID}"><Properties><Name>Child</Name>'
                "</Properties></Attribute>"
            ),
        )
    }
    assert (
        plan_metadata_three_way(tree, tree, tree)["objects"][0]["base_name"] == "Item"
    )


def test_semantic_output_is_deterministic_hash_only_and_does_not_mutate_trees():
    tree = {
        "CommonModules/Item.xml": metadata("CommonModule"),
        "CommonModules/Item/Ext/Module.bsl": b"SECRET_MODULE_PAYLOAD",
        "Orphan/Ext/Form.xml": f'<Form xmlns="{FORM_NS}"/>'.encode(),
    }
    original = copy.deepcopy(tree)
    first = plan_metadata_three_way(tree, tree, tree)
    reverse = dict(reversed(list(tree.items())))
    assert first == plan_metadata_three_way(reverse, reverse, reverse)
    assert tree == original
    assert "SECRET_MODULE_PAYLOAD" not in json.dumps(first)
    assert first["semantics"]["schema"] == 1
    assert first["semantics"]["mode"] == "read_only"
    assert first["scope"] == "metadata-object-v1"
    assert first["unsupported_files"] == [
        "CommonModules/Item/Ext/Module.bsl",
        "Orphan/Ext/Form.xml",
    ]


def test_dtd_in_form_remains_rejected_before_semantic_inspection():
    tree = {
        "CommonForms/Item.xml": metadata("CommonForm"),
        "CommonForms/Item/Ext/Form.xml": b"<!DOCTYPE Form><Form/>",
    }
    with pytest.raises(CoreError, match="DTD"):
        plan_metadata_three_way(tree, tree, tree)


def test_replacing_owner_uuid_at_same_path_is_not_a_supported_delete_add():
    base = {
        "CommonModules/Item.xml": metadata("CommonModule"),
        "CommonModules/Item/Ext/Module.bsl": b"Return 1;",
    }
    current = {
        **base,
        "CommonModules/Item.xml": metadata("CommonModule", identity=OTHER_UUID),
    }
    rows = semantic_rows(base, current, base)
    assert len(rows) == 2
    assert all(row["status"] == "unsupported" for row in rows)
    assert all(row["reason"] == "owner_identity_changed" for row in rows)


def test_missing_owner_in_one_version_does_not_authorize_companion_deletion():
    base = {
        "CommonModules/Item.xml": metadata("CommonModule"),
        "CommonModules/Item/Ext/Module.bsl": b"Return 1;",
    }
    current = {"CommonModules/Item/Ext/Module.bsl": b"Return 2;"}
    rows = semantic_rows(base, current, base)
    bound = next(row for row in rows if row["object_uuid"] is not None)
    assert bound["status"] == "unsupported"
    assert bound["reason"] == "owner_binding_incomplete"


@pytest.mark.parametrize(
    "kind,stem,tail,root,properties",
    [
        ("Form", "CommonForms/Item", "Form.xml", f'Form xmlns="{FORM_NS}"', ""),
        (
            "Template",
            "Templates/Item",
            "Template.xml",
            f'DataCompositionSchema xmlns="{DCS_NS}"',
            "<TemplateType>DataCompositionSchema</TemplateType>",
        ),
    ],
)
def test_disjoint_form_or_schema_edits_remain_atomic_conflicts(
    kind, stem, tail, root, properties
):
    def tree(left, right):
        return {
            stem + ".xml": metadata(kind, properties=properties),
            stem
            + "/Ext/"
            + tail: (
                f"<{root}><Left>{left}</Left><Right>{right}</Right>"
                f"</{root.split()[0]}>"
            ).encode(),
        }

    row = semantic_rows(tree(0, 0), tree(1, 0), tree(0, 1))[0]
    assert row["action"] == "conflict"
    assert row["status"] == "conflict"
    assert row["reason"] == "atomic_overlap"


def test_foreign_namespace_owner_does_not_bind_bsl_semantics():
    tree = {
        "CommonModules/Item.xml": metadata("CommonModule").replace(
            MD_NS.encode(), b"urn:foreign"
        ),
        "CommonModules/Item/Ext/Module.bsl": b"Return 1;",
    }
    row = semantic_rows(tree)[0]
    assert row["status"] == "unsupported"
    assert row["reason"] == "owner_namespace_unsupported"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-be", "utf-32", "utf-32-be"])
def test_non_utf8_xml_cannot_bypass_forbidden_declarations(encoding):
    raw = f'<!DOCTYPE Form [<!ENTITY x "unsafe">]><Form xmlns="{FORM_NS}">&x;</Form>'
    tree = {"CommonForms/Item/Ext/Form.xml": raw.encode(encoding)}
    with pytest.raises(CoreError, match="DTD|ENTITY"):
        plan_metadata_three_way(tree, tree, tree)
