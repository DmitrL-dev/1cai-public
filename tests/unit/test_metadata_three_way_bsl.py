"""Qualified BSL companions merge into one complete, owner-bound candidate."""

from collections.abc import Mapping
import copy
import hashlib
import json

import pytest

import rentgen_core.metadata_three_way as metadata_merge
from rentgen_core.errors import CoreError
from rentgen_core.three_way import plan_three_way


NS = "http://v8.1c.ru/8.3/MDClasses"
UUID = "11111111-1111-4111-8111-111111111111"
OTHER_UUID = "22222222-2222-4222-8222-222222222222"
OWNER = "Catalogs/Item.xml"
MODULE = "Catalogs/Item/Ext/ObjectModule.bsl"
BASE = b"first\nseparator\nlast\n"
CURRENT = b"ours\nseparator\nlast\n"
UPSTREAM = b"first\nseparator\ntheirs\n"
MERGED = b"ours\nseparator\ntheirs\n"
BOM = b"\xef\xbb\xbf"


def owner(kind="Catalog", *, name="Item", code="0", identity=UUID, extra=""):
    return (
        f'<MetaDataObject xmlns="{NS}"><{kind} uuid="{identity}">'
        f"<Properties><Name>{name}</Name><Code>{code}</Code></Properties>"
        f"<ChildObjects/>{extra}</{kind}></MetaDataObject>"
    ).encode()


def trees(values=(BASE, CURRENT, UPSTREAM)):
    return [{OWNER: owner(), MODULE: raw} for raw in values]


def materialize(*inputs, **limits):
    return metadata_merge.materialize_metadata_three_way(*inputs, **limits)


def blocked(inputs, *, reason=None, code="THREE_WAY_CONFLICT", **limits):
    before = copy.deepcopy(inputs)
    with pytest.raises(CoreError) as caught:
        materialize(*inputs, **limits)
    error = caught.value
    assert error.code == code
    assert "candidate" not in error.details
    assert "SECRET" not in json.dumps(error.to_dict("request"))
    assert inputs == before
    if reason:
        assert reason in {row["reason"] for row in error.details["blocking_scopes"]}
    return error


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("bom", [b"", BOM])
@pytest.mark.parametrize("final_newline", [False, True])
def test_disjoint_bsl_candidate_preserves_all_bytes(newline, bom, final_newline):
    def formatted(raw):
        raw = raw if final_newline else raw.rstrip(b"\n")
        return bom + raw.replace(b"\n", newline)

    inputs = trees(tuple(formatted(raw) for raw in (BASE, CURRENT, UPSTREAM)))
    before = copy.deepcopy(inputs)
    result = materialize(*inputs)
    expected = {OWNER: owner(), MODULE: formatted(MERGED)}
    assert result["candidate"] == expected
    assert result["candidate"][OWNER] is inputs[1][OWNER]
    assert inputs == before
    assert result["status"] == "ready"
    assert result["scope"] == "metadata-properties-v1"
    for label, tree in zip(
        ("base", "current", "upstream", "candidate"), (*inputs, expected)
    ):
        assert (
            result[label + "_digest"] == plan_three_way(tree, tree, tree)["base_digest"]
        )


@pytest.mark.parametrize(
    "kind,scope",
    [
        ("CommonModule", "Ext/Module.bsl"),
        ("Form", "Ext/Form/Module.bsl"),
        ("CommonForm", "Ext/Form/Module.bsl"),
        ("Catalog", "Ext/ObjectModule.bsl"),
        ("Document", "Ext/ManagerModule.bsl"),
        ("InformationRegister", "Ext/RecordSetModule.bsl"),
        ("Command", "Ext/CommandModule.bsl"),
        ("CommonModule", "eXt/MoDuLe.BSL"),
    ],
)
def test_recognized_bsl_scopes_use_existing_owner_contract(kind, scope):
    path = "Metadata/Item/" + scope
    inputs = [
        {"Metadata/Item.xml": owner(kind), path: raw}
        for raw in (BASE, CURRENT, UPSTREAM)
    ]
    assert materialize(*inputs)["candidate"] == {
        "Metadata/Item.xml": owner(kind),
        path: MERGED,
    }


@pytest.mark.parametrize(
    "values,expected",
    [
        ((BASE, BASE, BASE), BASE),
        ((BASE, BOM + b"ours\r\n", BASE), BOM + b"ours\r\n"),
        ((BASE, BASE, b"upstream\r\n\n"), b"upstream\r\n\n"),
        ((BASE, b"same\r", b"same\r"), b"same\r"),
        ((BASE, b"", BASE), b""),
        ((b"", BASE, b""), BASE),
    ],
)
def test_exact_bsl_actions_select_original_bytes(values, expected):
    inputs = trees(values)
    result = materialize(*inputs)
    assert result["candidate"][MODULE] == expected
    selected = (
        values[2] if values[1] == values[0] and values[1] != values[2] else values[1]
    )
    assert result["candidate"][MODULE] is selected
    assert result["counts"]["merged_objects"] == 0


@pytest.mark.parametrize("operation", ["add", "delete", "move"])
def test_exact_companion_path_actions_keep_existing_behavior(operation):
    inputs = trees((BASE, CURRENT, BASE))
    expected_path = MODULE
    if operation == "add":
        del inputs[0][MODULE]
        del inputs[2][MODULE]
    elif operation == "delete":
        del inputs[1][MODULE]
    else:
        inputs[1]["Catalogs/Moved.xml"] = inputs[1].pop(OWNER)
        expected_path = "Catalogs/Moved/Ext/ObjectModule.bsl"
        inputs[1][expected_path] = inputs[1].pop(MODULE)
    result = materialize(*inputs)
    assert result["candidate"] == inputs[1]
    if operation != "delete":
        assert result["candidate"][expected_path] is inputs[1][expected_path]


@pytest.mark.parametrize("change", ["name", "disjoint_properties"])
def test_owner_properties_and_bsl_can_merge_under_existing_xml_contract(change):
    inputs = trees()
    inputs[1][OWNER] = owner(name="Local")
    if change == "disjoint_properties":
        inputs[2][OWNER] = owner(code="1")
    result = materialize(*inputs)
    assert result["candidate"] == {
        OWNER: owner(
            name="Local", code="1" if change == "disjoint_properties" else "0"
        ),
        MODULE: MERGED,
    }
    assert result["counts"]["merged_objects"] == int(change == "disjoint_properties")


@pytest.mark.parametrize(
    "change", ["child", "wrapper", "comment", "properties_attribute"]
)
def test_unscoped_owner_xml_changes_block_composite_bsl(change):
    inputs = trees()
    if change == "child":
        inputs[1][OWNER] = owner(extra="<Unknown/>")
    elif change == "wrapper":
        inputs[1][OWNER] = owner().replace(
            b"<MetaDataObject ", b'<MetaDataObject version="2" '
        )
    elif change == "comment":
        inputs[1][OWNER] = owner().replace(
            b"<ChildObjects/>", b"<!--SECRET--><ChildObjects/>"
        )
    else:
        inputs[1][OWNER] = owner().replace(
            b"<Properties>", b'<Properties marker="SECRET">'
        )
    blocked(inputs)


def test_property_overlap_still_blocks_otherwise_mergeable_bsl():
    inputs = trees()
    inputs[1][OWNER] = owner(name="Local")
    inputs[2][OWNER] = owner(name="Remote")
    blocked(inputs, reason="object_conflict")


@pytest.mark.parametrize(
    "drift",
    [
        "owner_uuid",
        "owner_type",
        "owner_missing",
        "owner_move",
        "both_move",
        "scope",
        "scope_missing",
        "scope_added",
    ],
)
def test_owner_or_scope_drift_never_authorizes_composite_bsl(drift):
    inputs = trees()
    if drift == "owner_uuid":
        inputs[1][OWNER] = owner(identity=OTHER_UUID)
    elif drift == "owner_type":
        inputs[1][OWNER] = owner("Document")
    elif drift == "owner_missing":
        del inputs[1][OWNER]
    elif drift in {"owner_move", "both_move"}:
        inputs[1]["Catalogs/Moved.xml"] = inputs[1].pop(OWNER)
        if drift == "both_move":
            inputs[1]["Catalogs/Moved/Ext/ObjectModule.bsl"] = inputs[1].pop(MODULE)
    elif drift == "scope":
        inputs[1]["Catalogs/Item/Ext/ManagerModule.bsl"] = inputs[1].pop(MODULE)
    elif drift == "scope_missing":
        del inputs[1][MODULE]
    else:
        del inputs[0][MODULE]
    blocked(inputs)


@pytest.mark.parametrize(
    "invalid", ["orphan", "unknown_scope", "owner_type", "owner_namespace"]
)
def test_unsupported_bsl_binding_fails_even_on_exact_selection(invalid):
    inputs = trees((BASE, BASE, BASE))
    for tree in inputs:
        if invalid == "orphan":
            del tree[OWNER]
        elif invalid == "unknown_scope":
            tree["Catalogs/Item/Ext/Unknown.bsl"] = tree.pop(MODULE)
        elif invalid == "owner_type":
            tree[OWNER] = owner("CommonModule")
        else:
            tree[OWNER] = tree[OWNER].replace(NS.encode(), b"urn:foreign")
    blocked(inputs)


@pytest.mark.parametrize("invalid", [b"\xffSECRET", b"\x00SECRET", b"\xff\xfeS\x00"])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_every_bsl_version_must_be_utf8_without_nul(invalid, position):
    inputs = trees((BASE, BASE, BASE))
    inputs[position][MODULE] = invalid
    blocked(inputs, reason="bsl_encoding_unsupported")


@pytest.mark.parametrize(
    "current,upstream,reason",
    [
        (
            b"SECRET ours\nseparator\nlast\n",
            b"SECRET theirs\nseparator\nlast\n",
            "bsl_overlapping_edits",
        ),
        (
            b"SECRET ours\n" + BASE,
            b"SECRET theirs\n" + BASE,
            "bsl_same_anchor_insertions",
        ),
        (CURRENT, b"first\nSECRET separator\nlast\n", "bsl_overlapping_edits"),
        (CURRENT.replace(b"\n", b"\r\n"), UPSTREAM, "bsl_newline_style_changed"),
        (BOM + CURRENT, UPSTREAM, "bsl_bom_changed"),
        (b"ours\r\nseparator\nlast\n", UPSTREAM, "bsl_mixed_newlines"),
    ],
)
def test_primitive_conflicts_and_format_errors_are_metadata_blockers(
    current, upstream, reason
):
    blocked(trees((BASE, current, upstream)), reason=reason)


@pytest.mark.parametrize(
    "scope", ["form", "template", "extension", "unknown_bsl", "other_path"]
)
def test_other_blockers_cannot_be_bypassed_by_successful_bsl_merge(scope):
    inputs = trees()
    for index, tree in enumerate(inputs):
        if scope == "form":
            tree["CommonForms/Other.xml"] = owner("CommonForm", identity=OTHER_UUID)
            tree["CommonForms/Other/Ext/Form.xml"] = (
                f'<Form xmlns="http://v8.1c.ru/8.3/xcf/logform"><Value>{index}</Value></Form>'
            ).encode()
        elif scope == "template":
            tree["Templates/Other.xml"] = owner("Template", identity=OTHER_UUID)
            tree["Templates/Other/Ext/Template.xml"] = b"<Unknown/>"
        elif scope == "extension":
            tree[OWNER] = tree[OWNER].replace(
                b"</Properties>", b"<ObjectBelonging>Own</ObjectBelonging></Properties>"
            )
        elif scope == "unknown_bsl":
            tree["Catalogs/Item/Ext/Unknown.bsl"] = BASE
        else:
            tree["other.txt"] = str(index).encode()
    blocked(inputs)


def test_one_conflicting_module_prevents_partial_output_from_other_module():
    inputs = trees()
    for tree, raw in zip(inputs, (BASE, b"SECRET ours\n", b"SECRET theirs\n")):
        tree["Catalogs/Item/Ext/ManagerModule.bsl"] = raw
    blocked(inputs, reason="bsl_overlapping_edits")


def test_metadata_lowered_file_limit_bounds_combined_bsl_candidate():
    inputs = trees(
        (
            BASE,
            b"a" * 200 + b"\nseparator\nlast\n",
            b"first\nseparator\n" + b"z" * 200 + b"\n",
        )
    )
    limit = max(len(raw) for tree in inputs for raw in tree.values())
    blocked(inputs, max_file_bytes=limit, reason="bsl_candidate_byte_limit")


def test_metadata_total_limit_bounds_complete_candidate_after_bsl_merge():
    inputs = trees()
    limit = max(sum(map(len, tree.values())) for tree in inputs)
    inputs[1][MODULE] = CURRENT.replace(b"ours", b"ours-long")
    inputs[2][MODULE] = UPSTREAM.replace(b"theirs", b"theirs-long")
    limit = max(limit, *(sum(map(len, tree.values())) for tree in inputs))
    blocked(inputs, max_total_bytes=limit, code="THREE_WAY_LIMIT")


def test_metadata_cannot_raise_bsl_default_byte_limit():
    raw = b"x\n" * (8 * 1024 * 1024 + 1)
    inputs = trees((raw, b"ours\n" + raw, raw + b"theirs\n"))
    blocked(inputs, max_file_bytes=32 * 1024 * 1024, reason="bsl_byte_limit")


def test_bsl_diff_work_limit_remains_active():
    values = [
        b"".join(f"{label}{index}\n".encode() for index in range(2100))
        for label in ("base", "ours", "theirs")
    ]
    blocked(trees(values), reason="bsl_diff_work_limit")


def test_complete_candidate_keeps_unrelated_exact_actions():
    inputs = trees()
    inputs[0].update({"remove.txt": b"remove", "same.txt": b"old"})
    inputs[1].update({"same.txt": b"same", "local.txt": b"local"})
    inputs[2].update(
        {"remove.txt": b"remove", "same.txt": b"same", "remote.txt": b"remote"}
    )
    result = materialize(*inputs)
    assert result["candidate"] == {
        OWNER: owner(),
        MODULE: MERGED,
        "same.txt": b"same",
        "local.txt": b"local",
        "remote.txt": b"remote",
    }


def test_bsl_merge_uses_only_captured_mapping_snapshot():
    class CapturedOnce(Mapping):
        def __init__(self, content):
            self.content = content
            self.reads = 0

        def __getitem__(self, key):
            raise AssertionError("Original mapping read after capture")

        def __iter__(self):
            return iter(self.content)

        def __len__(self):
            return len(self.content)

        def items(self):
            self.reads += 1
            assert self.reads == 1
            return self.content.items()

    result = materialize(*(CapturedOnce(tree) for tree in trees()))
    assert result["candidate"][MODULE] == MERGED


def test_read_only_plan_stays_atomic_after_bsl_materialization():
    inputs = trees()
    before = metadata_merge.plan_metadata_three_way(*inputs)
    materialize(*inputs)
    assert metadata_merge.plan_metadata_three_way(*inputs) == before
    row = before["semantics"]["scopes"][0]
    assert (row["status"], row["reason"], row["granularity"]) == (
        "conflict",
        "atomic_overlap",
        "atomic_bytes",
    )


def test_bsl_merge_evidence_is_separate_deterministic_and_payload_free():
    inputs = trees((BASE, CURRENT.replace(b"ours", b"SECRET ours"), UPSTREAM))
    result = materialize(*inputs)
    assert result == materialize(
        *(dict(reversed(tuple(tree.items()))) for tree in inputs)
    )
    raw = result["candidate"][MODULE]
    assert result["counts"]["merged_objects"] == 0
    assert result["merged_objects"] == []
    assert result["counts"]["merged_bsl_scopes"] == 1
    assert result["merged_bsl_scopes"] == [
        {
            "object_type": "Catalog",
            "object_uuid": UUID,
            "scope": "Ext/ObjectModule.bsl",
            "candidate_path": MODULE,
            "candidate_sha256": hashlib.sha256(raw).hexdigest(),
            "candidate_size_bytes": len(raw),
        }
    ]
    assert "SECRET" not in json.dumps(
        {key: value for key, value in result.items() if key != "candidate"}
    )


def test_exact_actions_do_not_enter_bsl_diff_or_rewrite_branch_bytes(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Exact branch selection must not invoke BSL merge")

    monkeypatch.setattr(metadata_merge, "materialize_bsl_three_way", forbidden)
    inputs = trees((BASE, BOM + CURRENT.replace(b"\n", b"\r\n"), BASE))
    result = materialize(*inputs)
    assert result["candidate"][MODULE] is inputs[1][MODULE]
    assert "merged_bsl_scopes" not in result
    assert "merged_bsl_scopes_truncated" not in result
    assert "merged_bsl_scopes" not in result["counts"]


def test_composite_bsl_never_opens_files_or_starts_processes(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Pure metadata merge cannot open files or launch processes"
        )

    with monkeypatch.context() as patch:
        patch.setattr("builtins.open", forbidden)
        patch.setattr("os.open", forbidden)
        patch.setattr("subprocess.Popen", forbidden)
        result = materialize(*trees())
    assert result["candidate"] == {OWNER: owner(), MODULE: MERGED}


def test_unchanged_utf16_owner_does_not_require_xml_splicing_for_bsl_merge():
    inputs = trees()
    raw = owner().decode().encode("utf-16")
    for tree in inputs:
        tree[OWNER] = raw
    result = materialize(*inputs)
    assert result["candidate"] == {OWNER: raw, MODULE: MERGED}
    assert result["candidate"][OWNER] is raw


def test_bsl_evidence_is_bounded_without_truncating_the_candidate():
    inputs = [{}, {}, {}]
    for index in range(257):
        identity = f"{index:08x}-1111-4111-8111-111111111111"
        stem = f"Catalogs/Item{index}"
        for tree, raw in zip(inputs, (BASE, CURRENT, UPSTREAM)):
            tree[stem + ".xml"] = owner(identity=identity)
            tree[stem + "/Ext/ObjectModule.bsl"] = raw
    result = materialize(*inputs)
    assert len(result["candidate"]) == 514
    assert result["counts"]["merged_bsl_scopes"] == 257
    assert len(result["merged_bsl_scopes"]) == 256
    assert result["merged_bsl_scopes_truncated"] is True
    assert all(
        raw == MERGED
        for path, raw in result["candidate"].items()
        if path.endswith(".bsl")
    )


def test_bsl_conflict_evidence_is_bounded_and_never_returns_a_partial_tree():
    inputs = [{}, {}, {}]
    for index in range(257):
        identity = f"{index:08x}-1111-4111-8111-111111111111"
        stem = f"Catalogs/Item{index}"
        for tree, raw in zip(
            inputs, (BASE, b"SECRET ours\n" + BASE, b"SECRET theirs\n" + BASE)
        ):
            tree[stem + ".xml"] = owner(identity=identity)
            tree[stem + "/Ext/ObjectModule.bsl"] = raw
    error = blocked(inputs, reason="bsl_same_anchor_insertions")
    assert error.details["blocking_scope_count"] == 257
    assert len(error.details["blocking_scopes"]) == 256
    assert error.details["scopes_truncated"] is True
