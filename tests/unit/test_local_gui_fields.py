"""Real-Rust and loopback contracts for GUI-only child-field search."""
import hashlib
import sys

import pytest

from rentgen_core import metadata_field_search
from test_local_gui import running, upload
from test_local_gui_search import payload, search_wait, source, start
from test_metadata_field_search import attribute
from test_metadata_three_way_materialize import xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="GUI backend is Linux-only")
TARGET = "Catalogs/Fields.xml"


def owner(children, name="Fields"):
    return xml(name=name).replace(b'<ChildObjects/>', ('<ChildObjects>'+children+'</ChildObjects>').encode())


def test_gui_field_search_deduplicates_owners_preserves_provenance_and_root_inventory(running):
    app, server, _ = running
    child = attribute()
    section = '<TabularSection><Properties><Name>Rows</Name></Properties><ChildObjects>'+child+'</ChildObjects></TabularSection>'
    raw = owner(child+section+child)
    archive = zip_bytes({TARGET: raw, 'Catalogs/Other.xml': xml(name='Other')})
    job, outcome = upload(server, archive)
    initial = outcome['result']
    assert 'attribute_search' not in initial
    assert all('child_matches' not in row for row in initial['objects'])
    result = search_wait(server, start(server, payload(job, outcome, 'аРтИкУл')))['result']
    assert result['matching_objects'] == 1 and result['page']['total'] == 1
    row = result['objects'][0]
    assert row['name'] == 'Fields' and row['child_matching_total'] == 3
    assert not row['child_matches_truncated']
    assert [hit['child_index'] for hit in row['child_matches']] == [1, 1, 3]
    assert row['input_ref'] == {'relative_path': TARGET, 'input_sha256': hashlib.sha256(archive).hexdigest(), 'raw_sha256': hashlib.sha256(raw).hexdigest()}
    assert result['counts'] == initial['counts'] and result['by_type'] == initial['by_type']
    assert result['attribute_search']['fields_scanned'] == 3
    assert source(server, job, TARGET)[1]['text'].encode() == raw
    assert app.current.result == initial
    empty = search_wait(server, start(server, payload(job, outcome, '')))['result']
    assert 'attribute_search' not in empty and empty['matching_objects'] == 2
    missing = search_wait(server, start(server, payload(job, outcome, 'does-not-exist')))['result']
    assert missing['matching_objects'] == 0 and missing['attribute_search']['complete']


def test_child_hit_cap_reports_full_count(running):
    _, server, _ = running
    job, outcome = upload(server, zip_bytes({TARGET: owner(attribute()*25)}))
    result = search_wait(server, start(server, payload(job, outcome, 'КодПоставщика')))['result']
    row = result['objects'][0]
    assert len(row['child_matches']) == 20
    assert row['child_matching_total'] == 25 and row['child_matches_truncated']
    assert result['attribute_search']['fields_scanned'] == 25


def test_matching_owner_pagination_not_child_pagination(running):
    _, server, _ = running
    files = {f'Catalogs/Owner{i:03}.xml': owner(attribute()*2, f'Owner{i:03}') for i in range(201)}
    job, outcome = upload(server, zip_bytes(files))
    args = payload(job, outcome, 'КодПоставщика')
    first = search_wait(server, start(server, args))['result']
    assert first['matching_objects'] == 201 and len(first['objects']) == 200
    last = search_wait(server, start(server, {**args, 'offset': 200}))['result']
    assert last['page']['total'] == 201 and len(last['objects']) == 1
    assert last['objects'][0]['name'] == 'Owner200'
    assert last['attribute_search']['fields_scanned'] == 402
    assert all(row['child_matching_total'] == 2 for row in first['objects'])


@pytest.mark.parametrize('children,code', [
    ('<Attribute/>', 'METADATA_SEARCH_UNSUPPORTED'),
    (attribute('x'*513), 'METADATA_SEARCH_LIMIT_EXCEEDED'),
])
def test_incomplete_search_fails_without_successful_partial_list(running, children, code):
    _, server, _ = running
    job, outcome = upload(server, zip_bytes({TARGET: owner(children)}))
    result = search_wait(server, start(server, payload(job, outcome, 'absent')))
    assert result['status'] == 'error' and result['error'] == code
    assert 'result' not in result or result['result'] is None


def test_field_budget_exhaustion_explicit_not_zero_matches(running, monkeypatch):
    _, server, _ = running
    job, outcome = upload(server, zip_bytes({TARGET: owner(attribute()*3)}))
    monkeypatch.setattr(metadata_field_search, 'FIELD_LIMIT', 2)
    result = search_wait(server, start(server, payload(job, outcome, 'absent')))
    assert result['status'] == 'error' and result['error'] == 'METADATA_SEARCH_LIMIT_EXCEEDED'


def test_unsupported_designer_root_exposes_partial_zero_hit_coverage(running):
    _, server, _ = running
    files = {TARGET: owner(attribute()), 'Catalogs/Unknown.xml': b'<MetaDataObject><Unrecognized/></MetaDataObject>'}
    job, outcome = upload(server, zip_bytes(files))
    result = search_wait(server, start(server, payload(job, outcome, 'absent')))['result']
    assert result['matching_objects'] == 0
    assert result['attribute_search']['complete'] is False
    assert result['attribute_search']['unsupported_metadata_roots'] == 1
