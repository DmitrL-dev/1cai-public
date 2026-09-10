"""Discovery searches a verified complete snapshot, not the first general page."""
import pytest

import rentgen_core as api
import test_project_core_snapshot_resolver as fixtures

project = fixtures.project
scanner = fixtures.scanner
pytestmark = fixtures.pytestmark


def test_catalog_keeps_exact_paths_when_matching_unicode_casefold_and_module_suffixes():
    from rentgen_core.source_catalog import selected_entries, source_query

    entries = [
        {"layer_id": "base", "relative_path": "Продажи/Straße.BSL"},
        {"layer_id": "e1", "relative_path": "Продажи/Straße.OS"},
        {"layer_id": "e1", "relative_path": "Продажи/Straße.xml"},
        {"layer_id": "e1", "relative_path": "Продажи/Straße.bsl.bak"},
    ]
    document = {
        "source": {
            "entries": entries,
            "layers": [{"layer_id": "base"}, {"layer_id": "e1"}],
        }
    }
    assert (
        selected_entries(document, source_query(query="ПРОДАЖИ/STRASSE", kind="module"))
        == entries[:2]
    )
    assert (
        selected_entries(document, source_query(kind="module", layer="e1"))
        == entries[1:2]
    )


def test_module_search_precedes_pagination_and_preserves_pinned_sources(project):
    root = project[2].parents[3]
    for index in range(205):
        (root / f"A{index:03}.xml").write_bytes(b"<data/>")
    other = root / "CommonModules/ДругойМодуль/Ext/Module.bsl"
    other.parent.mkdir(parents=True)
    other.write_bytes(project[2].read_bytes())
    first = fixtures.publish(project)
    pinned = fixtures.selected(project)
    assert all(
        e.ref.relative_path.endswith(".xml")
        for e in pinned.sources.list_entries().entries
    )
    page = pinned.sources.list_entries(kind="module", query="МОДУЛЬ", limit=1)
    second = pinned.sources.list_entries(
        kind="module", query="МОДУЛЬ", limit=1, cursor=page.next_cursor
    )
    assert page.next_cursor and second.next_cursor is None
    assert {e.ref.relative_path for e in page.entries + second.entries} == {
        "CommonModules/ДругойМодуль/Ext/Module.bsl",
        "CommonModules/ОбщийМодуль/Ext/Module.bsl",
    }
    exact = pinned.sources.list_entries(
        kind="module", query="общиймодуль", layer="base"
    )
    assert (
        exact.entries[0].ref.relative_path == "CommonModules/ОбщийМодуль/Ext/Module.bsl"
    )
    assert pinned.sources.read_source(exact.entries[0].ref) == project[2].read_bytes()
    assert (
        pinned.sources.list_entries(kind="module", query="нет такого пути").entries
        == ()
    )
    for changed in (
        {"query": "модуль"},
        {"kind": "all"},
        {"layer": "base"},
        {"limit": 2},
    ):
        options = {
            "kind": "module",
            "query": "МОДУЛЬ",
            "limit": 1,
            "cursor": page.next_cursor,
            **changed,
        }
        with pytest.raises(api.CoreError) as error:
            pinned.sources.list_entries(**options)
        assert error.value.code == "INVALID_SOURCE_CURSOR"
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"3"))
    fixtures.publish(project)
    assert (
        pinned.sources.list_entries(kind="module", query="общиймодуль")
        .entries[0]
        .ref.snapshot
        == first.snapshot
    )
    with pytest.raises(api.CoreError) as error:
        fixtures.selected(project).sources.list_entries(
            kind="module", query="МОДУЛЬ", limit=1, cursor=page.next_cursor
        )
    assert error.value.code == "INVALID_SOURCE_CURSOR"


def test_invalid_source_filters_are_explicit_errors(project):
    fixtures.publish(project)
    sources = fixtures.selected(project).sources
    for options in (
        {"query": None},
        {"query": "x" * 257},
        {"query": "\ud800"},
        {"query": "x\x00"},
        {"query": "x\u202e"},
        {"kind": "bsl"},
        {"layer": ""},
        {"layer": True},
        {"layer": "not-present"},
    ):
        with pytest.raises(api.CoreError) as error:
            sources.list_entries(**options)
        assert error.value.code == "INVALID_QUERY_OPTIONS"
