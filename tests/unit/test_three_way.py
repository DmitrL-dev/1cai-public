"""Three-way source planning is deterministic and never writes input trees."""

from collections.abc import Mapping

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.three_way import materialize_three_way, plan_three_way


def test_plan_classifies_safe_changes_and_conflicts_without_content_output():
    base = {
        "CommonModules/A.bsl": b"base-a",
        "CommonModules/B.bsl": b"base-b",
        "CommonModules/C.bsl": b"base-c",
        "CommonModules/D.bsl": b"base-d",
    }
    current = {
        "CommonModules/A.bsl": b"base-a",
        "CommonModules/B.bsl": b"custom-b",
        "CommonModules/C.bsl": b"custom-c",
        "CommonModules/D.bsl": b"custom-d",
        "CommonModules/Local.bsl": b"local",
    }
    upstream = {
        "CommonModules/A.bsl": b"upstream-a",
        "CommonModules/B.bsl": b"upstream-b",
        "CommonModules/C.bsl": b"base-c",
        "CommonModules/D.bsl": b"custom-d",
        "CommonModules/Remote.bsl": b"remote",
    }

    result = plan_three_way(base, current, upstream)

    assert result["scope"] == "path-bytes-v1"
    assert result["counts"] == {
        "unchanged": 0,
        "same_change": 1,
        "keep_current": 2,
        "take_upstream": 2,
        "conflict": 1,
    }
    changes = {item["path"]: item for item in result["changes"]}
    assert changes["CommonModules/A.bsl"]["action"] == "take_upstream"
    assert changes["CommonModules/B.bsl"]["action"] == "conflict"
    assert changes["CommonModules/C.bsl"]["action"] == "keep_current"
    assert changes["CommonModules/D.bsl"]["action"] == "same_change"
    assert changes["CommonModules/Local.bsl"]["action"] == "keep_current"
    assert changes["CommonModules/Remote.bsl"]["action"] == "take_upstream"
    assert all("content" not in item for item in result["changes"])


def test_plan_is_deterministic_and_distinguishes_deletion_conflict():
    args = (
        {"A.bsl": b"a", "B.bsl": b"b"},
        {"B.bsl": b"custom-b"},
        {"A.bsl": b"upstream", "B.bsl": b"b"},
    )
    first = plan_three_way(*args)
    second = plan_three_way(*args)
    assert first == second
    assert {item["path"]: item for item in first["changes"]}["A.bsl"][
        "action"
    ] == "conflict"
    assert {item["path"]: item for item in first["changes"]}["B.bsl"][
        "action"
    ] == "keep_current"


@pytest.mark.parametrize(
    "trees",
    [
        ({"../bad.bsl": b"x"}, {}, {}),
        ({"A.bsl": "text"}, {}, {}),
        ({"A.bsl": b"x"}, {"a.bsl": b"y"}, {}),
    ],
)
def test_plan_rejects_unsafe_or_ambiguous_inputs(trees):
    with pytest.raises(CoreError):
        plan_three_way(*trees)


def test_plan_enforces_file_and_byte_bounds():
    with pytest.raises(CoreError, match="limit"):
        plan_three_way({"A.bsl": b"x"}, {}, {}, max_files=0)
    with pytest.raises(CoreError, match="limit"):
        plan_three_way({"A.bsl": b"xx"}, {}, {}, max_file_bytes=1)
    with pytest.raises(CoreError, match="limit"):
        plan_three_way({"A.bsl": b"x"}, {"B.bsl": b"x"}, {"C.bsl": b"x"}, max_files=2)


def test_materialize_builds_only_unambiguous_candidate_and_preserves_inputs():
    base = {
        "A.bsl": b"base-a",
        "B.bsl": b"base-b",
        "C.bsl": b"base-c",
        "Deleted.bsl": b"remove-me",
    }
    current = {
        "A.bsl": b"base-a",
        "B.bsl": b"custom-b",
        "C.bsl": b"same-c",
    }
    upstream = {
        "A.bsl": b"upstream-a",
        "B.bsl": b"base-b",
        "C.bsl": b"same-c",
        "Added.bsl": b"new-upstream",
    }

    before = (base.copy(), current.copy(), upstream.copy())
    result = materialize_three_way(base, current, upstream)

    assert result["schema"] == 1
    assert result["scope"] == "path-bytes-v1"
    assert result["status"] == "ready"
    assert result["candidate"] == {
        "A.bsl": b"upstream-a",
        "B.bsl": b"custom-b",
        "C.bsl": b"same-c",
        "Added.bsl": b"new-upstream",
    }
    assert result["candidate"]["B.bsl"] is current["B.bsl"]
    assert (base, current, upstream) == before


def test_materialize_rejects_any_conflict_without_partial_candidate():
    with pytest.raises(CoreError) as error:
        materialize_three_way(
            {"Module.bsl": b"base"},
            {"Module.bsl": b"local"},
            {"Module.bsl": b"upstream"},
        )

    assert error.value.code == "THREE_WAY_CONFLICT"
    assert error.value.details == {
        "conflicting_paths": ["Module.bsl"],
        "conflict_count": 1,
    }


def test_materialize_uses_the_validated_snapshot_when_mapping_drifts_after_items():
    class DriftingMapping(Mapping):
        def __init__(self):
            self._planned = {"Module.bsl": b"base"}
            self._drifted = {"Module.bsl": b"not-planned"}

        def __getitem__(self, key):
            return self._drifted[key]

        def __iter__(self):
            return iter(self._planned)

        def __len__(self):
            return len(self._planned)

        def items(self):
            return self._planned.items()

    current = DriftingMapping()
    result = materialize_three_way(
        {"Module.bsl": b"base"}, current, {"Module.bsl": b"base"}
    )

    assert result["candidate"] == {"Module.bsl": b"base"}
