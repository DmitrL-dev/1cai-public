"""Pure comparison of producer inventories; no XML or native merge claims."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json

import pytest

import rentgen_core as api
from rentgen_core.edt_identity_three_way import (
    EDTIdentityThreeWayLimits,
    plan_edt_identity_three_way,
)

PROJECT = "12345678-1234-4234-8234-123456789abc"
ROOT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CHILD = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OTHER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
PATH = "Catalogs/Products/Products.mdo"
LAYER = {
    "layer_id": "base",
    "ordinal": 0,
    "kind": "base",
    "configuration_uuid": None,
    "identity_status": "unresolved",
    "source_format": "edt",
}
LIMITS = {
    "max_input_bytes": 8 * 1024**2,
    "max_objects": 20_000,
    "max_owners": 20_000,
    "max_layers": 64,
    "max_rows": 20_000,
}


def inventory(snapshot="a", *, name="Article", digest="1", child=True):
    ref = {
        "snapshot": {
            "project_id": PROJECT,
            "snapshot_id": snapshot * 64,
            "manifest_hash": snapshot * 64,
        },
        "layer_id": "base",
        "relative_path": PATH,
        "raw_sha256": digest * 64,
    }
    root = {
        "canonical_uuid": ROOT,
        "observed_uuid": ROOT,
        "type": "Catalog",
        "name": "Products",
        "xml_path": "/Catalog",
        "owner": None,
        "layer": deepcopy(LAYER),
        "source_ref": deepcopy(ref),
    }
    item = {
        "canonical_uuid": CHILD,
        "observed_uuid": CHILD,
        "type": "Attribute",
        "name": name,
        "xml_path": "/Catalog/attributes[1]",
        "owner": {
            "canonical_uuid": ROOT,
            "source_ref": deepcopy(ref),
            "xml_path": "/Catalog",
        },
        "layer": deepcopy(LAYER),
        "source_ref": deepcopy(ref),
    }
    return {
        "snapshot": deepcopy(ref["snapshot"]),
        "parser": "edt_identity_v1",
        "identity_scope": "snapshot_layer",
        "coverage": "partial",
        "owner_basis": "direct_xml_containment_only",
        "layer_basis": "pinned_snapshot_declaration",
        "layers": [
            {
                **LAYER,
                "parsed_mdo_files": 1,
                "unparsed_files": 0,
                "count_basis": "verified_manifest_paths",
            }
        ],
        "objects": [root, item] if child else [root],
        "source_refs": [ref],
        "validation_summary": {
            "generation": {
                **ref["snapshot"],
                "source_digest": "2" * 64,
                "graph_hash": "3" * 64,
                "verified_source_files": 1,
                "verified_derived_files": 2,
                "verified_source_bytes": 100,
                "verified_total_bytes": 200,
                "all_expected_files_verified": True,
                "inventory_checks": "entry_exit",
                "expected_bytes_protected": "retained_handles",
                "temporal_namespace_atomicity": "not_proven",
            }
        },
    }


def row(result, uuid=CHILD, layer="base"):
    return next(
        item
        for item in result["objects"]
        if item["key"] == {"layer_id": layer, "canonical_uuid": uuid}
    )


@pytest.mark.parametrize(
    "current,upstream,action",
    [
        ("Article", "Article", "unchanged"),
        ("SKU", "SKU", "same_change"),
        ("SKU", "Article", "keep_current"),
        ("Article", "SKU", "take_upstream"),
        ("SKU", "Code", "conflict"),
    ],
)
def test_exact_identity_actions_ignore_snapshot_differences(current, upstream, action):
    inputs = [inventory(), inventory("b", name=current), inventory("c", name=upstream)]
    result = plan_edt_identity_three_way(*inputs)
    assert row(result)["action"] == action
    assert {
        key: result[key]
        for key in (
            "schema",
            "scope",
            "mode",
            "coverage",
            "materialization",
            "native_validation",
        )
    } == {
        "schema": 1,
        "scope": "edt-identity-v1",
        "mode": "read_only",
        "coverage": "partial",
        "materialization": "unavailable",
        "native_validation": "unavailable",
    }
    assert result["counts"]["objects"] == 2
    assert (
        sum(
            result["counts"][name]
            for name in (
                "unchanged",
                "same_change",
                "keep_current",
                "take_upstream",
                "conflict",
                "unsupported",
            )
        )
        == 2
    )
    for label, source in zip(("base", "current", "upstream"), inputs):
        assert result["inputs"][label]["snapshot"] == source["snapshot"]
        canonical = json.dumps(
            source,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        assert result["inputs"][label]["digest"] == sha256(canonical).hexdigest()
        assert row(result)[label]["source_size_bytes"] is None
    assert api.plan_edt_identity_three_way is plan_edt_identity_three_way
    assert api.EDTIdentityThreeWayLimits is EDTIdentityThreeWayLimits


@pytest.mark.parametrize(
    "present,action",
    [
        ((False, False, True), "take_upstream"),
        ((False, True, False), "keep_current"),
        ((False, True, True), "same_change"),
        ((True, False, True), "keep_current"),
        ((True, True, False), "take_upstream"),
        ((True, False, False), "same_change"),
    ],
)
def test_add_delete_requires_retained_owner(present, action):
    values = [
        inventory(version, child=exists) for version, exists in zip("abc", present)
    ]
    result = row(plan_edt_identity_three_way(*values))
    assert result["action"] == action
    for label, exists in zip(("base", "current", "upstream"), present):
        assert (result[label] is not None) == exists


def test_delete_modify_conflicts_and_hashes_are_file_evidence():
    result = plan_edt_identity_three_way(
        inventory(), inventory("b", child=False), inventory("c", digest="4")
    )
    assert row(result)["action"] == "conflict"
    assert row(result, ROOT)["action"] == "take_upstream"


def test_missing_owner_in_absent_version_is_unsupported():
    missing = inventory("b", child=False)
    missing["objects"] = []
    missing["source_refs"] = []
    missing["layers"][0]["parsed_mdo_files"] = 0
    result = plan_edt_identity_three_way(inventory(), missing, inventory("c"))
    assert row(result)["action"] == "unsupported"
    assert row(result)["reason"] == "missing_owner_evidence"
    assert row(result, ROOT)["action"] == "keep_current"


def test_order_is_by_layer_ordinal_layer_id_and_uuid():
    value = inventory()
    value["objects"].reverse()
    result = plan_edt_identity_three_way(value, inventory("b"), inventory("c"))
    assert [item["key"]["canonical_uuid"] for item in result["objects"]] == [
        ROOT,
        CHILD,
    ]
    assert [item["action"] for item in result["objects"]] == ["unchanged", "unchanged"]


@pytest.mark.parametrize("name", LIMITS)
@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "above"])
def test_limits_are_positive_lower_only_integers(name, bad):
    with pytest.raises(api.CoreError) as error:
        EDTIdentityThreeWayLimits(**{name: LIMITS[name] + 1 if bad == "above" else bad})
    assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_limits_type_and_defaults():
    assert asdict(EDTIdentityThreeWayLimits()) == LIMITS
    assert plan_edt_identity_three_way(
        inventory(), inventory(), inventory(), limits=None
    )
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(inventory(), inventory(), inventory(), limits={})
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("name", ["max_input_bytes", "max_objects", "max_rows"])
def test_exceeded_limits_never_return_partial_rows(name):
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(
            inventory(),
            inventory(),
            inventory(),
            limits=EDTIdentityThreeWayLimits(**{name: 1}),
        )
    assert error.value.code == "EDT_IDENTITY_PLAN_LIMIT"


def test_mapping_is_captured_once_and_never_read_after_normalization():
    class Once(Mapping):
        def __init__(self, value):
            self.value, self.reads = value, set()

        def __iter__(self):
            return iter(self.value)

        def __len__(self):
            return len(self.value)

        def __getitem__(self, key):
            assert key not in self.reads, "Input mapping reread"
            self.reads.add(key)
            return self.value[key]

    value = Once(inventory())
    result = plan_edt_identity_three_way(value, inventory("b"), inventory("c"))
    assert row(result)["action"] == "unchanged"


def test_mapping_iteration_failure_is_payload_free():
    class Drift(Mapping):
        def __iter__(self):
            raise RuntimeError("PRIVATE_PAYLOAD")

        def __len__(self):
            return 1

        def __getitem__(self, key):
            raise RuntimeError("PRIVATE_PAYLOAD")

    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(Drift(), inventory(), inventory())
    assert error.value.code == "EDT_IDENTITY_PLAN_INVALID"
    assert "PRIVATE_PAYLOAD" not in str(error.value)
    assert error.value.details == {}


@pytest.mark.parametrize(
    "case",
    [
        "project",
        "snapshot",
        "foreign_ref",
        "hash",
        "uuid",
        "observed_uuid",
        "schema",
        "coverage",
        "profile",
        "owner_basis",
        "layer_basis",
        "duplicate_object",
        "duplicate_layer",
        "duplicate_ref",
        "missing_ref",
        "missing_owner",
        "owner_ref",
        "owner_path",
        "unknown_row",
        "unknown_generation",
        "size_bool",
        "size_nan",
        "size_negative",
        "owner_cycle",
        "xml_location",
        "layer_binding",
        "ref_hash_disagreement",
        "source_count",
        "generation_snapshot",
    ],
)
def test_malformed_inventory_and_bindings_are_payload_free(case):
    bad = inventory("b")
    item = bad["objects"][1]
    generation = bad["validation_summary"]["generation"]
    if case == "project":
        bad = json.loads(json.dumps(bad).replace(PROJECT, OTHER))
    elif case == "snapshot":
        bad["snapshot"]["manifest_hash"] = "f" * 64
    elif case == "foreign_ref":
        item["source_ref"]["snapshot"]["snapshot_id"] = "a" * 64
        item["source_ref"]["snapshot"]["manifest_hash"] = "a" * 64
    elif case == "hash":
        item["source_ref"]["raw_sha256"] = "PRIVATE_PAYLOAD"
    elif case == "uuid":
        item["canonical_uuid"] = "PRIVATE_PAYLOAD"
    elif case == "observed_uuid":
        item["observed_uuid"] = OTHER
    elif case == "schema":
        bad["schema"] = 1
    elif case in {"coverage", "owner_basis", "layer_basis"}:
        bad[case] = "PRIVATE_PAYLOAD"
    elif case == "profile":
        bad["parser"] = "PRIVATE_PAYLOAD"
    elif case == "duplicate_object":
        bad["objects"].append(deepcopy(item))
    elif case == "duplicate_layer":
        bad["layers"].append(deepcopy(bad["layers"][0]))
    elif case == "duplicate_ref":
        bad["source_refs"].append(deepcopy(bad["source_refs"][0]))
    elif case == "missing_ref":
        bad["source_refs"] = []
    elif case == "missing_owner":
        bad["objects"].pop(0)
    elif case == "owner_ref":
        item["owner"]["source_ref"]["raw_sha256"] = "e" * 64
    elif case == "owner_path":
        item["owner"]["xml_path"] = "/PRIVATE_PAYLOAD"
    elif case == "unknown_row":
        item["xml"] = "PRIVATE_PAYLOAD"
    elif case == "unknown_generation":
        generation["payload"] = "PRIVATE_PAYLOAD"
    elif case.startswith("size_"):
        generation["verified_source_bytes"] = {
            "size_bool": True,
            "size_nan": float("nan"),
            "size_negative": -1,
        }[case]
    elif case == "owner_cycle":
        item["owner"]["canonical_uuid"] = CHILD
    elif case == "xml_location":
        item["xml_path"] = "/Catalog/attributes[01]"
    elif case == "layer_binding":
        item["layer"]["ordinal"] = 1
    elif case == "ref_hash_disagreement":
        item["source_ref"]["raw_sha256"] = "f" * 64
    elif case == "source_count":
        generation["verified_source_files"] = 0
    else:
        generation["snapshot_id"] = "c" * 64
        generation["manifest_hash"] = "c" * 64
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(inventory(), bad, inventory("c"))
    assert error.value.code == "EDT_IDENTITY_PLAN_INVALID"
    assert error.value.details == {}
    assert "PRIVATE_PAYLOAD" not in str(error.value)


def rename_root(value, name="Renamed"):
    old = value["objects"][0]["name"]
    result = json.loads(json.dumps(value).replace(old, name))
    return result


@pytest.mark.parametrize(
    "change,reason",
    [
        ("type", "type_changed"),
        ("owner", "owner_changed"),
        ("path", "owner_path_changed"),
        ("layer_declaration", "layer_changed"),
        ("layer_id", "layer_changed"),
    ],
)
def test_identity_binding_changes_are_unsupported(change, reason):
    changed = inventory("b")
    child = changed["objects"][1]
    if change == "type":
        child["type"] = "Form"
        child["xml_path"] = "/Catalog/forms[1]"
    elif change == "owner":
        changed = json.loads(json.dumps(changed).replace(ROOT, OTHER))
    elif change == "path":
        changed = rename_root(changed)
    elif change == "layer_declaration":
        changed["layers"][0].update(ordinal=1, kind="extension")
        for item in changed["objects"]:
            item["layer"].update(ordinal=1, kind="extension")
    else:
        changed = json.loads(json.dumps(changed).replace('"base"', '"extra"'))
        changed["layers"][0]["kind"] = "extension"
        changed["layers"][0]["ordinal"] = 1
        for item in changed["objects"]:
            item["layer"]["kind"] = "extension"
            item["layer"]["ordinal"] = 1
    result = plan_edt_identity_three_way(inventory(), changed, inventory("c"))
    assert row(result)["action"] == "unsupported"
    assert row(result)["reason"] == reason


def test_root_rename_preserves_uuid_but_child_owner_path_is_unsupported():
    result = plan_edt_identity_three_way(
        inventory(), rename_root(inventory("b")), inventory("c")
    )
    assert row(result, ROOT)["action"] == "keep_current"
    assert row(result)["reason"] == "owner_path_changed"


def test_missing_selected_layer_prevents_inferred_deletion():
    absent = inventory("b")
    absent["layers"] = absent["objects"] = absent["source_refs"] = []
    result = plan_edt_identity_three_way(inventory(), absent, inventory("c"))
    assert all(item["reason"] == "missing_layer_evidence" for item in result["objects"])


def test_uppercase_observed_uuid_and_hashes_do_not_create_changes():
    base = inventory(digest="e")
    changed = inventory("b", digest="e")
    for item in changed["objects"]:
        item["observed_uuid"] = item["observed_uuid"].upper()
    changed = json.loads(json.dumps(changed).replace("e" * 64, "E" * 64))
    result = plan_edt_identity_three_way(base, changed, inventory("c", digest="e"))
    assert all(item["action"] == "unchanged" for item in result["objects"])


def test_dynamically_allocated_mapping_values_do_not_alias_each_other():
    class Dynamic(Mapping):
        def __init__(self, value):
            self.value = value

        def __iter__(self):
            return iter(self.value)

        def __len__(self):
            return len(self.value)

        def __getitem__(self, key):
            return deepcopy(self.value[key])

    result = plan_edt_identity_three_way(
        *(Dynamic(inventory(version)) for version in "abc")
    )
    assert all(item["action"] == "unchanged" for item in result["objects"])


@pytest.mark.parametrize("name", ["max_objects", "max_owners", "max_layers"])
def test_limits_cover_union_not_only_each_version(name):
    changed = inventory("b")
    if name == "max_objects":
        changed = json.loads(json.dumps(changed).replace(CHILD, OTHER))
        maximum = 2
    elif name == "max_owners":
        changed = json.loads(json.dumps(changed).replace(ROOT, OTHER))
        maximum = 1
    else:
        changed = json.loads(json.dumps(changed).replace('"base"', '"extra"'))
        changed["layers"][0]["kind"] = "base"
        for item in changed["objects"]:
            item["layer"]["kind"] = "base"
        maximum = 1
    limits = EDTIdentityThreeWayLimits(**{name: maximum})
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(inventory(), changed, inventory("c"), limits=limits)
    assert error.value.code == "EDT_IDENTITY_PLAN_LIMIT"


def test_output_byte_cap_refuses_large_plan_without_truncation():
    value = inventory()
    child = value["objects"].pop()
    for index in range(3500):
        item = deepcopy(child)
        item["canonical_uuid"] = item[
            "observed_uuid"
        ] = f"10000000-0000-4000-8000-{index:012x}"
        item["name"] = f"A{index}"
        item["xml_path"] = f"/Catalog/attributes[{index + 1}]"
        value["objects"].append(item)
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(value, value, value)
    assert error.value.code == "OUTPUT_LIMIT_EXCEEDED"


def layered(value):
    result = deepcopy(value)
    extra = deepcopy(value)
    for item in extra["layers"] + [row["layer"] for row in extra["objects"]]:
        item.update(layer_id="extra", ordinal=1, kind="extension")
    for item in extra["source_refs"]:
        item["layer_id"] = "extra"
    for item in extra["objects"]:
        item["source_ref"]["layer_id"] = "extra"
        if item["owner"]:
            item["owner"]["source_ref"]["layer_id"] = "extra"
    for key in ("layers", "objects", "source_refs"):
        result[key].extend(extra[key])
    result["validation_summary"]["generation"]["verified_source_files"] = 2
    return result


def test_stable_same_uuid_in_two_layers_remains_separate_observations():
    base, current, upstream = [layered(inventory(version)) for version in "abc"]
    current["objects"].reverse()
    current["layers"].reverse()
    current["source_refs"].reverse()
    result = plan_edt_identity_three_way(base, current, upstream)
    assert [item["key"] for item in result["objects"]] == [
        {"layer_id": layer, "canonical_uuid": uuid}
        for layer in ("base", "extra")
        for uuid in (ROOT, CHILD)
    ]
    assert all(item["action"] == "unchanged" for item in result["objects"])


@pytest.mark.parametrize(
    "case", ["ordinal", "root", "kind", "configuration_uuid", "identity_status"]
)
def test_ambiguous_or_fabricated_layer_declarations_are_invalid(case):
    value = layered(inventory())
    if case == "ordinal":
        value["layers"][1]["ordinal"] = 0
    elif case == "root":
        value["layers"][1]["root_relative_path"] = "base"
    elif case in {"configuration_uuid", "identity_status"}:
        value["layers"][1][case] = "PRIVATE_PAYLOAD"
    else:
        value["layers"][1]["kind"] = "base"
        for item in value["objects"][2:]:
            item["layer"]["kind"] = "base"
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(value, inventory(), inventory())
    assert error.value.code == "EDT_IDENTITY_PLAN_INVALID"


@pytest.mark.parametrize("version", [0, 1, 2])
@pytest.mark.parametrize(
    "kind,tag", [("Form", "forms"), ("TabularSection", "tabularSections")]
)
@pytest.mark.parametrize("reverse", [False, True])
def test_different_child_kinds_cannot_share_a_physical_xml_position(
    version, kind, tag, reverse
):
    inputs = [inventory(label) for label in "abc"]
    objects = inputs[version]["objects"]
    extra = deepcopy(objects[1])
    extra.update(
        canonical_uuid=OTHER,
        observed_uuid=OTHER,
        type=kind,
        name="PRIVATE_PAYLOAD",
        xml_path=f"/Catalog/{tag}[1]",
    )
    objects.append(extra)
    if reverse:
        objects.reverse()
    with pytest.raises(api.CoreError) as error:
        plan_edt_identity_three_way(*inputs)
    assert error.value.code == "EDT_IDENTITY_PLAN_INVALID"
    assert error.value.details == {}
    assert "PRIVATE_PAYLOAD" not in str(error.value)


def test_sibling_indices_are_scoped_to_direct_owner_xml_location():
    value = inventory()
    section = deepcopy(value["objects"][1])
    section.update(
        canonical_uuid=OTHER,
        observed_uuid=OTHER,
        type="TabularSection",
        name="Lines",
        xml_path="/Catalog/tabularSections[2]",
    )
    nested = deepcopy(value["objects"][1])
    nested.update(
        canonical_uuid="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        observed_uuid="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        xml_path=section["xml_path"] + "/attributes[1]",
    )
    nested["owner"].update(canonical_uuid=OTHER, xml_path=section["xml_path"])
    value["objects"].extend([section, nested])
    result = plan_edt_identity_three_way(value, value, value)
    assert result["counts"]["unchanged"] == 4
    assert all(item["action"] == "unchanged" for item in result["objects"])
