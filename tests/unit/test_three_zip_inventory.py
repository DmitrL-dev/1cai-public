"""Manifest-only three-way decisions, bounds, and fail-closed disclosure."""
from copy import deepcopy
from itertools import product

import pytest

from rentgen_core.errors import CoreError
from rentgen_core import three_zip_inventory as inventory


A = ("a" * 64, 1)
B = ("b" * 64, 2)
C = ("c" * 64, 3)
VALUES = (None, A, B, C)
# Rows=current None/A/B/C; columns=upstream None/A/B/C, for each base.
EXPECTED = (
    (("unchanged", "take_upstream", "take_upstream", "take_upstream"),
     ("keep_current", "same_change", "conflict", "conflict"),
     ("keep_current", "conflict", "same_change", "conflict"),
     ("keep_current", "conflict", "conflict", "same_change")),
    (("same_change", "keep_current", "conflict", "conflict"),
     ("take_upstream", "unchanged", "take_upstream", "take_upstream"),
     ("conflict", "keep_current", "same_change", "conflict"),
     ("conflict", "keep_current", "conflict", "same_change")),
    (("same_change", "conflict", "keep_current", "conflict"),
     ("conflict", "same_change", "keep_current", "conflict"),
     ("take_upstream", "take_upstream", "unchanged", "take_upstream"),
     ("conflict", "conflict", "keep_current", "same_change")),
    (("same_change", "conflict", "conflict", "keep_current"),
     ("conflict", "same_change", "conflict", "keep_current"),
     ("conflict", "conflict", "same_change", "keep_current"),
     ("take_upstream", "take_upstream", "take_upstream", "unchanged")),
)


def evidence(value):
    return None if value is None else {"raw_sha256": value[0], "size_bytes": value[1]}


def entries(items):
    return tuple({"entry_id": index, "path": path, **evidence(value)}
                 for index, (path, value) in enumerate(items) if value is not None)


def one(value, path="CommonModules/ОбщийМодуль/Ext/Module.bsl"):
    return () if value is None else entries([(path, value)])


def classify(*sides, checkpoint=lambda: None):
    return inventory.classify_entries(*sides, checkpoint=checkpoint)


def page(rows, offset=0, action="all", checkpoint=lambda: None):
    return inventory.page_entries(rows, offset, action, checkpoint=checkpoint)


@pytest.mark.parametrize("indices", tuple(product(range(4), repeat=3)))
def test_all_64_absent_a_b_c_combinations(indices):
    values = tuple(VALUES[index] for index in indices)
    sides = tuple(one(value) for value in values)
    original = deepcopy(sides)
    rows, counts, coverage = classify(*sides)
    expected = EXPECTED[indices[0]][indices[1]][indices[2]]
    assert sides == original
    if indices == (0, 0, 0):
        assert rows == ()
        assert counts == dict.fromkeys((*inventory.ACTIONS, "total", "files", "changes"), 0)
    else:
        assert rows == ({"path": "CommonModules/ОбщийМодуль/Ext/Module.bsl", "action": expected,
                         **dict(zip(inventory.SIDES, (evidence(value) for value in values)))},)
        assert counts == {**{action: int(action == expected) for action in inventory.ACTIONS},
                          "total": 1, "files": 1, "changes": int(expected != "unchanged")}
    assert coverage == {"scope": "exact_path_inventory", "comparison": "raw_sha256_and_size",
                        "complete": True, "entry_records": sum(value is not None for value in values),
                        "decoded_bytes": sum(value[1] for value in values if value is not None),
                        "union_paths": len(rows),
                        "side_entries": dict(zip(inventory.SIDES, (int(value is not None) for value in values))),
                        "side_decoded_bytes": dict(zip(inventory.SIDES, (value[1] if value else 0 for value in values)))}


def test_digest_and_size_are_both_evidence_without_byte_or_semantic_claims():
    rows, counts, coverage = classify(one(A), one((A[0], 2)), one((A[0], 3)))
    assert rows[0]["action"] == "conflict"
    assert counts["conflict"] == 1
    assert coverage["comparison"] == "raw_sha256_and_size"
    assert set(rows[0]) == {"path", "action", "base", "current", "upstream"}
    assert set(rows[0]["base"]) == {"raw_sha256", "size_bytes"}


def test_unchanged_additions_deletions_divergence_are_counted_over_union():
    cases = {
        "unchanged": (A, A, A), "current_add": (None, B, None),
        "upstream_add": (None, None, B), "same_add": (None, B, B),
        "conflict_add": (None, B, C), "current_delete": (A, None, A),
        "upstream_delete": (A, A, None), "both_delete": (A, None, None),
        "delete_edit": (A, None, B), "edit_delete": (A, B, None),
        "same_edit": (A, B, B), "divergent_edit": (A, B, C),
    }
    sides = tuple(entries([(path, values[index]) for path, values in cases.items() if values[index] is not None])
                  for index in range(3))
    rows, counts, _ = classify(*sides)
    assert {row["path"]: row["action"] for row in rows} == {
        "unchanged": "unchanged", "current_add": "keep_current", "upstream_add": "take_upstream",
        "same_add": "same_change", "conflict_add": "conflict", "current_delete": "keep_current",
        "upstream_delete": "take_upstream", "both_delete": "same_change", "delete_edit": "conflict",
        "edit_delete": "conflict", "same_edit": "same_change", "divergent_edit": "conflict",
    }
    assert counts == {"unchanged": 1, "same_change": 3, "keep_current": 2, "take_upstream": 2,
                      "conflict": 4, "total": 12, "files": 12, "changes": 11}


def test_utf8_path_order_exact_unicode_paths_and_no_input_or_output_aliasing():
    paths = ["😀.xml", "Я.xml", "é.xml", "a.xml", "Z.xml", "Cafe\u0301/Один.xml"]
    side = entries([(path, A) for path in paths])
    rows, counts, coverage = classify(side, side, side)
    assert [row["path"] for row in rows] == sorted(paths, key=lambda path: path.encode("utf-8"))
    reversed_side = entries([(path, A) for path in reversed(paths)])
    assert classify(reversed_side, reversed_side, reversed_side) == (rows, counts, coverage)
    side[0]["raw_sha256"] = C[0]
    assert rows[-1]["base"] == evidence(A)
    disclosure = page(rows)
    disclosure["rows"][0]["base"]["size_bytes"] = 100
    assert rows[0]["base"]["size_bytes"] == 1
    assert rows[0]["current"]["size_bytes"] == 1


@pytest.mark.parametrize("side", range(3))
@pytest.mark.parametrize("bad", [None, {}, set(), iter(()), "", b"", 1, True])
def test_non_list_manifest_rejected_on_every_side(side, bad):
    sides = [(), (), ()]
    sides[side] = bad
    with pytest.raises(CoreError) as error:
        classify(*sides)
    assert error.value.code == "THREE_ZIP_INVENTORY_INVALID"


@pytest.mark.parametrize("mutation", [
    {"entry_id": True}, {"entry_id": 0.0}, {"entry_id": -1}, {"entry_id": 1},
    {"raw_sha256": "A" * 64}, {"raw_sha256": "g" * 64}, {"raw_sha256": "a" * 63},
    {"raw_sha256": "a" * 65}, {"raw_sha256": "a" * 64 + "\n"}, {"raw_sha256": None},
    {"raw_sha256": b"a" * 64}, {"size_bytes": True}, {"size_bytes": 1.0},
    {"size_bytes": -1}, {"size_bytes": "1"}, {"size_bytes": None}, {"path": None},
    {"path": 1}, {"path": b"a"}, {"extra": "field"},
])
@pytest.mark.parametrize("side", range(3))
def test_malformed_fields_rejected_independently(side, mutation):
    sides = [(), (), ()]
    sides[side] = one(A)
    sides[side][0].update(mutation)
    with pytest.raises(CoreError) as error:
        classify(*sides)
    assert error.value.code == "THREE_ZIP_INVENTORY_INVALID"


@pytest.mark.parametrize("field", ["entry_id", "path", "raw_sha256", "size_bytes"])
def test_missing_fields_rejected(field):
    value = one(A)
    del value[0][field]
    with pytest.raises(CoreError):
        classify(value, (), ())


@pytest.mark.parametrize("bad", [None, [], (), "entry", 1])
def test_non_dictionary_entry_rejected(bad):
    with pytest.raises(CoreError):
        classify((bad,), (), ())


@pytest.mark.parametrize("path", ["", ".", "..", "../a", "a/../b", "/a", "a/", "a//b", "a/./b",
                                  "a\\b", "C:/a", "a\0b", "a\nb", "CON", "com1.txt", "a/aux.txt",
                                  "a.", "a ", "a/<b", "a/|b", "a/?b", "a/*b", "\ud800", "\udfff",
                                  "a" * 1025, "Я" * 513])
def test_unsafe_or_oversized_paths_rejected(path):
    with pytest.raises(CoreError) as error:
        classify(one(A, path), (), ())
    assert error.value.code == "THREE_ZIP_INVENTORY_INVALID"


@pytest.mark.parametrize("path", ["a" * 1024, "Я" * 512])
def test_path_byte_limit_is_inclusive(path):
    assert classify(one(A, path), (), ())[0][0]["path"] == path


COLLISIONS = [
    ("a.bsl", "A.bsl"), ("é.bsl", "e\u0301.bsl"), ("Straße.bsl", "STRASSE.bsl"),
    ("Dir/a.bsl", "dir/b.bsl"), ("é/a", "e\u0301/b"),
    ("Dir", "Dir/a.bsl"), ("DIR", "Dir/a.bsl"),
    ("Outer/Inner", "Outer/Inner/a.bsl"), ("Outer/Inner/a", "Outer/inner/b"),
]


@pytest.mark.parametrize("names", COLLISIONS)
@pytest.mark.parametrize("sides", [(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)])
def test_union_case_nfc_and_file_directory_aliases_rejected(names, sides):
    values = [(), (), ()]
    for side, name in zip(sides, names):
        values[side] = one(A, name)
    with pytest.raises(CoreError) as error:
        classify(*values)
    assert error.value.code == "THREE_ZIP_INVENTORY_INVALID"


@pytest.mark.parametrize("names", [*COLLISIONS, ("a", "a")])
@pytest.mark.parametrize("reverse", [False, True])
def test_same_manifest_aliases_and_duplicate_paths_rejected(names, reverse):
    names = reversed(names) if reverse else names
    with pytest.raises(CoreError):
        classify(entries([(name, A) for name in names]), (), ())


def test_duplicate_entry_id_rejected():
    side = entries([("a", A), ("b", B)])
    side[1]["entry_id"] = 0
    with pytest.raises(CoreError):
        classify(side, (), ())


@pytest.mark.parametrize("side", range(3))
def test_per_side_entry_and_byte_limits(side):
    sides = [(), (), ()]
    sides[side] = entries([(f"f{n:04}", A) for n in range(4097)])
    with pytest.raises(CoreError) as error:
        classify(*sides)
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"
    sides[side] = one((A[0], inventory.MAX_FILE_BYTES + 1))
    with pytest.raises(CoreError) as error:
        classify(*sides)
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"
    sides[side] = entries([(f"f{n}", (A[0], inventory.MAX_FILE_BYTES)) for n in range(8)] + [("last", A)])
    with pytest.raises(CoreError) as error:
        classify(*sides)
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"


def test_inclusive_zero_file_side_and_aggregate_byte_boundaries():
    side = entries([(f"f{n}", (A[0], inventory.MAX_FILE_BYTES)) for n in range(8)] + [("empty", (B[0], 0))])
    rows, counts, coverage = classify(side, side, side)
    assert len(rows) == 9
    assert counts["unchanged"] == 9
    assert coverage["decoded_bytes"] == inventory.MAX_TOTAL_BYTES == 96 * 1024**2
    assert coverage["side_decoded_bytes"] == dict.fromkeys(inventory.SIDES, 32 * 1024**2)


def test_aggregate_record_and_byte_caps_are_enforced_explicitly(monkeypatch):
    monkeypatch.setattr(inventory, "MAX_ENTRY_RECORDS", 2)
    with pytest.raises(CoreError) as error:
        classify(one(A), one(A), one(A))
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"
    monkeypatch.setattr(inventory, "MAX_ENTRY_RECORDS", 12288)
    monkeypatch.setattr(inventory, "MAX_TOTAL_BYTES", 2)
    with pytest.raises(CoreError) as error:
        classify(one(A), one(A), one(A))
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"


@pytest.fixture
def maximum_inventory():
    return classify(*(entries([(f"{side}/f{n:04}", A) for n in range(4096)]) for side in inventory.SIDES))


def test_4096_each_12288_records_and_union_paths_accepted(maximum_inventory):
    rows, counts, coverage = maximum_inventory
    assert len(rows) == counts["total"] == coverage["entry_records"] == coverage["union_paths"] == 12288
    assert coverage["side_entries"] == dict.fromkeys(inventory.SIDES, 4096)
    assert counts["keep_current"] == counts["same_change"] == counts["take_upstream"] == 4096
    first = page(rows)
    assert first["page"] == {"offset": 0, "limit": 200, "total": 12288, "returned": 200,
                              "has_previous": False, "has_next": True}
    last = page(rows, offset=12200)
    assert last["page"] == {"offset": 12200, "limit": 200, "total": 12288, "returned": 88,
                             "has_previous": True, "has_next": False}
    assert last["rows"] == list(rows[12200:])


def test_union_limit_enforced_explicitly(monkeypatch):
    monkeypatch.setattr(inventory, "MAX_ROWS", 2)
    with pytest.raises(CoreError) as error:
        classify(one(A, "a"), one(A, "b"), one(A, "c"))
    assert error.value.code == "THREE_ZIP_INVENTORY_LIMIT"


@pytest.mark.parametrize("action", ["all", "changes", *inventory.ACTIONS])
def test_filters_have_exact_full_filtered_totals_and_keep_full_counts(action):
    sides = tuple(entries([(f"{b}{c}{u}", VALUES[(b, c, u)[side]])
                           for b, c, u in product(range(4), repeat=3)
                           if VALUES[(b, c, u)[side]] is not None]) for side in range(3))
    rows, counts, coverage = classify(*sides)
    original = deepcopy((rows, counts, coverage))
    result = page(rows, action=action)
    expected = [row for row in rows if action == "all" or row["action"] == action
                or (action == "changes" and row["action"] != "unchanged")]
    assert result["rows"] == expected
    assert result["page"]["total"] == result["page"]["returned"] == len(expected)
    assert (rows, counts, coverage) == original
    assert counts["total"] == 63


@pytest.mark.parametrize("offset", [-1, 1, 199, 201, 12201, 12400, True, 0.0, "0", None])
def test_invalid_page_offsets_rejected(offset):
    with pytest.raises(CoreError) as error:
        page((), offset=offset)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("action", ["conflicts", "added", "", None, [], 0, True])
def test_invalid_filters_rejected(action):
    with pytest.raises(CoreError) as error:
        page((), action=action)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_empty_page_and_out_of_range_filtered_page():
    assert page(())["page"] == {"offset": 0, "limit": 200, "total": 0, "returned": 0,
                                "has_previous": False, "has_next": False}
    rows, _, _ = classify(entries([(f"f{n:04}", A) for n in range(400)]), (), ())
    assert page(rows, offset=200)["page"]["has_next"] is False
    assert page(rows, action="conflict")["rows"] == []
    for offset, action in ((400, "all"), (200, "conflict")):
        with pytest.raises(CoreError) as error:
            page(rows, offset=offset, action=action)
        assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("operation", ["classify", "page"])
@pytest.mark.parametrize("code", ["CANCELLED", "ACCESS_DENIED", "PARENT_BUDGET_EXCEEDED"])
def test_checkpoint_denial_after_display_cap_yields_no_partial_result(operation, code):
    side = entries([(f"f{n:04}", A) for n in range(401)])
    rows = classify(side, (), ())[0]
    calls = 0
    denial = CoreError(code, "Stop now")

    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == 9:
            raise denial

    with pytest.raises(CoreError) as error:
        if operation == "classify":
            classify(side, (), (), checkpoint=checkpoint)
        else:
            page(rows, checkpoint=checkpoint)
    assert error.value is denial
    assert calls == 9


@pytest.mark.parametrize("operation", ["classify", "page"])
def test_final_checkpoint_is_required_before_disclosure(operation):
    calls = 0
    reject_at = None

    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == reject_at:
            raise CoreError("ACCESS_DENIED", "Revoked at final checkpoint")

    invoke = (lambda: classify(one(A), (), (), checkpoint=checkpoint)) if operation == "classify" else (
        lambda: page(classify(one(A), (), ())[0], checkpoint=checkpoint))
    invoke()
    reject_at, calls = calls, 0
    with pytest.raises(CoreError) as error:
        invoke()
    assert error.value.code == "ACCESS_DENIED"
    assert calls == reject_at


@pytest.mark.parametrize("clock_name,budget", [("monotonic", "WALL_SECONDS"), ("thread_time", "CPU_SECONDS")])
@pytest.mark.parametrize("operation", ["classify", "page"])
def test_cooperative_budget_denial_propagates_without_result(monkeypatch, clock_name, budget, operation):
    elapsed = 0
    monkeypatch.setattr(inventory.time, clock_name, lambda: elapsed)

    def checkpoint():
        nonlocal elapsed
        elapsed = getattr(inventory, budget)

    with pytest.raises(CoreError) as error:
        if operation == "classify":
            classify((), (), (), checkpoint=checkpoint)
        else:
            page((), checkpoint=checkpoint)
    assert error.value.code == "THREE_ZIP_INVENTORY_BUDGET_EXCEEDED"


def test_checkpoint_is_required_and_not_saved_as_authorization():
    with pytest.raises(TypeError):
        inventory.classify_entries((), (), ())
    with pytest.raises(CoreError):
        classify((), (), (), checkpoint=None)
    rows = classify(one(A), (), ())[0]
    with pytest.raises(CoreError) as error:
        page(rows, checkpoint=lambda: (_ for _ in ()).throw(CoreError("ACCESS_DENIED", "Now denied")))
    assert error.value.code == "ACCESS_DENIED"


@pytest.mark.parametrize("mutation", [
    lambda row: row.update(extra=True), lambda row: row.pop("base"),
    lambda row: row.update(path="../x"), lambda row: row.update(action="conflict"),
    lambda row: row.update(base=None), lambda row: row["base"].update(size_bytes=True),
])
def test_pager_rejects_malformed_cached_rows(mutation):
    rows = classify(one(A), (), ())[0]
    mutation(rows[0])
    with pytest.raises(CoreError):
        page(rows)


def test_pager_rejects_oversized_unordered_and_duplicate_rows():
    rows = classify(entries([("a", A), ("b", B)]), (), ())[0]
    for invalid in ((rows[1], rows[0]), (rows[0], rows[0]), (rows[0],) * 12289, {}, (None,)):
        with pytest.raises(CoreError):
            page(invalid)


def test_punctuation_cannot_hide_a_union_file_directory_collision():
    with pytest.raises(CoreError):
        classify(one(A, "a"), one(B, "a!"), one(C, "a/b"))


def test_punctuation_cannot_hide_implicit_directory_aliases():
    with pytest.raises(CoreError):
        classify(one(A, "A/z"), one(B, "a!"), one(C, "a/y"))


def test_deep_paths_use_linear_path_storage_and_preserve_names():
    deep = "/".join(["a"] * 500)
    rows, _, _ = classify(one(A, deep + "/x"), one(B, deep + "/y"), one(C, deep + "/z"))
    assert [row["path"] for row in rows] == [deep + "/" + leaf for leaf in "xyz"]


@pytest.mark.parametrize("values,expected", [
    ((None, ("e" * 64, 0), None), "keep_current"),
    ((("e" * 64, 0), None, ("e" * 64, 0)), "keep_current"),
    ((("e" * 64, 0), ("e" * 64, 0), None), "take_upstream"),
    ((("e" * 64, 0), None, A), "conflict"),
    ((("e" * 64, 0), ("e" * 64, 0), ("e" * 64, 0)), "unchanged"),
])
def test_absence_is_distinct_from_empty_file_evidence(values, expected):
    rows, _, _ = classify(*(one(value) for value in values))
    assert rows[0]["action"] == expected
    assert [rows[0][label] for label in inventory.SIDES] == [evidence(value) for value in values]


@pytest.mark.parametrize("operation", ["classify", "page"])
def test_fresh_authorization_callbacks_are_at_most_32_steps_apart(operation, monkeypatch):
    sides = tuple(entries([(f"{label}/deep/f{n:04}", A) for n in range(100)]) for label in inventory.SIDES)
    rows = classify(*sides)[0]
    steps, boundaries = 0, []
    original = inventory._Checkpoint.step

    def step(self):
        nonlocal steps
        steps += 1
        original(self)

    monkeypatch.setattr(inventory._Checkpoint, "step", step)
    checkpoint = lambda: boundaries.append(steps)
    if operation == "classify":
        classify(*sides, checkpoint=checkpoint)
    else:
        page(rows, checkpoint=checkpoint)
    assert boundaries[0] == 0
    assert boundaries[-1] == steps
    gaps = [end - start for start, end in zip(boundaries, boundaries[1:])]
    assert max(gaps) == 32
    assert all(0 <= gap <= 32 for gap in gaps)


@pytest.mark.parametrize("operation", ["classify", "page"])
def test_revocation_within_batch_is_observed_at_next_checkpoint(operation, monkeypatch):
    side = entries([(f"f{n:04}", A) for n in range(300)])
    rows = classify(side, (), ())[0]
    steps = 0
    denied = False
    original = inventory._Checkpoint.step

    def step(self):
        nonlocal steps, denied
        steps += 1
        if steps == 201:
            denied = True
        original(self)

    def checkpoint():
        if denied:
            raise CoreError("ACCESS_DENIED", "Revoked within a bounded batch")

    monkeypatch.setattr(inventory._Checkpoint, "step", step)
    with pytest.raises(CoreError) as error:
        if operation == "classify":
            classify(side, (), (), checkpoint=checkpoint)
        else:
            page(rows, checkpoint=checkpoint)
    assert error.value.code == "ACCESS_DENIED"
    assert steps == 224


@pytest.mark.parametrize("clock_name,budget", [("monotonic", "WALL_SECONDS"), ("thread_time", "CPU_SECONDS")])
def test_local_budget_checked_between_authorization_boundaries(monkeypatch, clock_name, budget):
    elapsed = 0
    calls = 0
    monkeypatch.setattr(inventory.time, clock_name, lambda: elapsed)

    def checkpoint():
        nonlocal calls
        calls += 1

    check = inventory._Checkpoint(checkpoint)
    check()
    elapsed = getattr(inventory, budget)
    with pytest.raises(CoreError) as error:
        check.step()
    assert error.value.code == "THREE_ZIP_INVENTORY_BUDGET_EXCEEDED"
    assert calls == 1
