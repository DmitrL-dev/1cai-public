"""Pure bounded field extraction plus GUI HTTP integration over owned Rust bytes."""
from xml.sax.saxutils import escape

import pytest

from rentgen_core import metadata_field_search as fields
from rentgen_core.errors import CoreError
from rentgen_core.metadata_xml import parse_xml


def attribute(name="КодПоставщика", *, kind="Attribute", synonym="Артикул поставщика"):
    return f'<{kind} uuid="same-observed-uuid"><Properties><Name>{escape(name)}</Name><Synonym><item><lang>ru</lang><content>{escape(synonym)}</content></item></Synonym></Properties></{kind}>'


def metadata(children, namespace=""):
    return parse_xml(f'<Catalog {namespace}><Properties><Name>Owner</Name></Properties><ChildObjects>{children}</ChildObjects></Catalog>'.encode())


def search(children, query="поставщика", namespace=""):
    worker = fields.FieldSearch(lambda: None)
    return worker, worker.match(metadata(children, namespace), query.casefold())


def test_namespaced_direct_fields_nested_tabular_and_duplicate_positions():
    child = attribute()
    section = '<TabularSection><Properties><Name>Строки</Name></Properties><ChildObjects>'+child+'</ChildObjects></TabularSection>'
    worker, (rows, total) = search(child+attribute(kind="Dimension")+attribute(kind="Resource")+section+child, namespace='xmlns="urn:designer"')
    assert total == 5 and len(rows) == 5
    assert [r["child_index"] for r in rows] == [1, 2, 3, 1, 5]
    assert rows[3]["parent_index"] == 4 and rows[3]["parent_name"] == "Строки"
    assert rows[3]["parent_type"] == "TabularSection"
    assert rows[0]["parent_name"] is None and rows[0]["parent_index"] is None
    assert all(r["uuid_status"] == "unverified" for r in rows)
    assert worker.coverage() == {"scope": fields.SCOPE, "fields_scanned": 5, "tabular_sections_scanned": 1, "unsupported_metadata_roots": 0, "complete": True}


@pytest.mark.parametrize("query", ["кОдПоСтАвЩиКа", "АРТИКУЛ", "aTtRiBuTe"])
def test_casefold_name_synonym_and_canonical_type(query):
    assert search(attribute(), query)[1][1] == 1


def test_non_fields_and_arbitrary_deep_nodes_not_claimed():
    child = attribute()
    wrapped = '<Form><ChildObjects>'+child+'</ChildObjects></Form>'
    nested = '<TabularSection><Properties><Name>HiddenParent</Name></Properties><ChildObjects><Dimension><Properties><Name>Hidden</Name></Properties></Dimension>'+wrapped+'</ChildObjects></TabularSection>'
    worker, result = search(wrapped+nested, "hidden")
    assert result == ([], 0)
    assert worker.coverage()["fields_scanned"] == 0
    assert worker.coverage()["tabular_sections_scanned"] == 1


def test_matching_count_keeps_duplicates_but_bounds_returned_rows():
    worker, (rows, total) = search(attribute()*25)
    assert total == 25 and len(rows) == 20
    assert [r["child_index"] for r in rows] == list(range(1, 21))
    assert worker.coverage()["fields_scanned"] == 25


def test_html_text_remains_data():
    _, (rows, total) = search(attribute('<img src=x onerror=owned()>'), "<img")
    assert total == 1 and rows[0]["name"] == '<img src=x onerror=owned()>'


@pytest.mark.parametrize("children", ['<Attribute/>', '<TabularSection/>'])
def test_missing_known_properties_rejects_search(children):
    with pytest.raises(CoreError) as error:
        search(children)
    assert error.value.code == "METADATA_SEARCH_UNSUPPORTED"


@pytest.mark.parametrize("name", ["x"*513, "я"*257])
def test_oversized_text_rejects_even_without_match(name):
    with pytest.raises(CoreError) as error:
        search(attribute(name), "absent")
    assert error.value.code == "METADATA_SEARCH_LIMIT_EXCEEDED"


def test_inventory_budget_is_global_across_owners(monkeypatch):
    monkeypatch.setattr(fields, "FIELD_LIMIT", 2)
    worker = fields.FieldSearch(lambda: None)
    worker.match(metadata(attribute()*2), "absent")
    with pytest.raises(CoreError) as error:
        worker.match(metadata(attribute()), "absent")
    assert error.value.code == "METADATA_SEARCH_LIMIT_EXCEEDED"


@pytest.mark.parametrize("clock", ["wall", "cpu"])
def test_expired_budget_rejects_before_success(clock):
    worker = fields.FieldSearch(lambda: None)
    setattr(worker, clock, -1000)
    with pytest.raises(CoreError) as error:
        worker.match(metadata(attribute()), "absent")
    assert error.value.code == "METADATA_SEARCH_BUDGET_EXCEEDED"


def test_authorization_and_cancellation_checked_between_fields():
    calls = []
    def authorize():
        calls.append(1)
        if len(calls) >= 3:
            raise CoreError("CANCELLED", "cancelled")
    worker = fields.FieldSearch(authorize)
    with pytest.raises(CoreError) as error:
        worker.match(metadata(attribute()*5), "поставщика")
    assert error.value.code == "CANCELLED"


@pytest.mark.parametrize("raw,code", [
    (b'<Catalog><ChildObjects>', "XML_INVALID"),
    (b'<!DOCTYPE Catalog [<!ENTITY a "expanded">]><Catalog>&a;</Catalog>', "XML_FORBIDDEN"),
    (('<Catalog>'+ '<x>'*64+'</x>'*64+'</Catalog>').encode(), "METADATA_LIMIT_EXCEEDED"),
    (b'<Catalog>'+b' '* (4*1024*1024)+b'</Catalog>', "METADATA_LIMIT_EXCEEDED"),
])
def test_existing_xml_safety_boundary(raw, code):
    with pytest.raises(CoreError) as error:
        parse_xml(raw)
    assert error.value.code == code


def test_unsupported_roots_make_field_coverage_partial():
    worker = fields.FieldSearch(lambda: None)
    assert worker.coverage(2)["complete"] is False
    assert worker.coverage(2)["unsupported_metadata_roots"] == 2


def test_all_localized_field_synonyms_match_with_exact_locale_evidence():
    child = '<Attribute><Properties><Name>Field</Name><Synonym><item><lang>ru</lang><content>Русское имя</content></item><item><lang>en</lang><content>SupplierSKU</content></item></Synonym></Properties></Attribute>'
    worker, (rows, total) = search(child, 'suppliersku')
    assert total == 1 and rows[0]['synonym'] == 'SupplierSKU'
    assert rows[0]['synonym_locale'] == 'en' and worker.coverage()['complete']
    assert search(child, 'Field')[1][0][0]['synonym'] == 'Русское имя'
    assert search(child, 'русское')[1][0][0]['synonym_locale'] == 'ru'


@pytest.mark.parametrize('child', [
    '<Attribute><Properties><Name>First</Name></Properties><Properties><Name>Hidden</Name></Properties></Attribute>',
    '<Attribute><Properties><Name>First</Name><Name>Hidden</Name></Properties></Attribute>',
    '<Attribute><Properties><Name>Field</Name><Synonym>First</Synonym><Synonym>Hidden</Synonym></Properties></Attribute>',
    '<TabularSection><Properties><Name>Rows</Name></Properties><ChildObjects/><ChildObjects><Attribute><Properties><Name>Hidden</Name></Properties></Attribute></ChildObjects></TabularSection>',
    '<Attribute><Properties><Synonym><item><lang>ru</lang><content>First</content><content>Hidden</content></item></Synonym></Properties></Attribute>',
    '<Attribute><Properties><Name><Hidden/></Name></Properties></Attribute>',
])
def test_duplicate_or_nested_known_field_structure_rejected(child):
    with pytest.raises(CoreError) as error:
        search(child, 'hidden')
    assert error.value.code == 'METADATA_SEARCH_UNSUPPORTED'


def test_duplicate_owner_childobjects_rejected_even_if_first_empty():
    meta = parse_xml(('<Catalog><Properties><Name>Owner</Name></Properties><ChildObjects/><ChildObjects>'+attribute()+'</ChildObjects></Catalog>').encode())
    with pytest.raises(CoreError) as error:
        fields.FieldSearch(lambda: None).match(meta, 'absent')
    assert error.value.code == 'METADATA_SEARCH_UNSUPPORTED'


def test_ambiguous_owner_properties_rejected_in_field_search():
    meta = parse_xml(b'<Catalog><Properties><Name>Owner</Name></Properties><Properties><Name>Hidden</Name></Properties><ChildObjects/></Catalog>')
    with pytest.raises(CoreError) as error:
        fields.FieldSearch(lambda: None).match(meta, 'hidden')
    assert error.value.code == 'METADATA_SEARCH_UNSUPPORTED'


def test_oversized_unmatched_locale_rejects_without_hiding_it():
    child = '<Attribute><Properties><Name>Field</Name><Synonym><item><lang>ru</lang><content>Match</content></item><item><lang>en</lang><content>'+'x'*513+'</content></item></Synonym></Properties></Attribute>'
    with pytest.raises(CoreError) as error:
        search(child, 'match')
    assert error.value.code == 'METADATA_SEARCH_LIMIT_EXCEEDED'
