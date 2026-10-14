"""Pure occurrence positions, bounded paging/scans and input validation."""
import pytest

from rentgen_core import source_occurrences as occurrences
from rentgen_core.errors import CoreError


def scan(text, query, offset=0, checkpoint=lambda: None):
    return occurrences._scan(text, query, offset, checkpoint)


def positions(rows):
    return [(row['line'], row['column'], row['offset']) for row in rows]


def test_unicode_codepoint_columns_mixed_newlines_tabs_and_no_normalization():
    text = '😀x needle\r\n\tneedle\rабneedle\nneedle\u2028needle\né e\u0301'
    rows, total = scan(text, 'needle')
    assert total == 5
    assert positions(rows) == [(1, 4, 3), (2, 2, 12), (3, 3, 21), (4, 1, 28), (4, 8, 35)]
    assert [r['excerpt'] for r in rows] == ['😀x needle', '\tneedle', 'абneedle', 'needle\u2028needle', 'needle\u2028needle']
    assert scan(text, 'é')[1] == 1 and scan(text, 'e\u0301')[1] == 1
    assert scan(text, 'Needle')[1] == 0
    assert scan(text, '\tneedle')[0][0]['column'] == 1


def test_literal_overlapping_and_regex_characters_are_data():
    rows, total = scan('aaaa\r\naaaa .* [x]', 'aa')
    assert total == 6 and positions(rows) == [(1, 1, 0), (1, 2, 1), (1, 3, 2), (2, 1, 6), (2, 2, 7), (2, 3, 8)]
    assert scan('aaaa .* [x]', '.*')[1] == 1
    assert scan('aaaa .* [x]', '[x]')[1] == 1


@pytest.mark.parametrize('text', ['', '\r', '\n', '\r\n', '\n\r\r\n'], ids=['empty','cr','lf','crlf','mixed'])
def test_empty_or_only_newlines_is_complete_empty(text):
    calls = []
    assert scan(text, 'x', checkpoint=lambda: calls.append(1)) == ([], 0)
    assert calls


@pytest.mark.parametrize('prefix,line,column', [('', 1, 1), ('\r', 2, 1), ('\n', 2, 1), ('\r\n', 2, 1), ('\r\r\n\n', 4, 1), ('😀\t', 1, 3)], ids=['empty','cr','lf','crlf','mixed','emoji-tab'])
def test_line_and_column_start_conventions(prefix, line, column):
    rows, total = scan(prefix+'needle', 'needle')
    assert total == 1 and positions(rows) == [(line, column, len(prefix))]


def test_cross_chunk_literal_and_crlf_are_not_lost_or_double_counted(monkeypatch):
    monkeypatch.setattr(occurrences, 'SCAN_CHARS', 8)
    rows, total = scan('xxxxxxneedle\r\nneedle'+'aaaaaa', 'needle')
    assert total == 2 and positions(rows) == [(1, 7, 6), (2, 1, 14)]
    rows, total = scan('xxxxxxx\r\nneedle', 'needle')
    assert positions(rows) == [(2, 1, 9)] and total == 1
    assert scan('a'*17, 'aa')[1] == 16


def test_excerpt_bounds_contain_maximum_query_and_are_single_logical_line():
    query = 'q'*256
    text = 'earlier\r\n'+'x'*1000+query+'z'*1000+'\nnext'
    rows, total = scan(text, query)
    row = rows[0]
    assert total == 1 and len(row['excerpt']) == 512 and query in row['excerpt']
    assert row['line'] == 2 and row['column'] == 1001
    assert row['truncated_before'] and row['truncated_after']
    assert '\r' not in row['excerpt'] and '\n' not in row['excerpt']
    row = scan('abcneedle\nnext', 'needle')[0][0]
    assert row['excerpt'] == 'abcneedle' and not row['truncated_before'] and not row['truncated_after']
    # A line ending exactly at the snippet bound is not truncated.
    row = scan('needle'+'x'*506+'\r\nnext', 'needle')[0][0]
    assert len(row['excerpt']) == 512 and not row['truncated_after']


def test_all_overlapping_hits_are_counted_after_first_page_and_last_page():
    text = 'a' * occurrences.SOURCE_FILE_LIMIT
    rows, total = scan(text, 'a')
    assert total == 262144 and len(rows) == 200
    assert rows[0]['offset'] == 0 and rows[-1]['offset'] == 199
    rows, total = scan(text, 'a', 262000)
    assert total == 262144 and len(rows) == 144
    assert rows[0]['offset'] == 262000 and rows[-1]['offset'] == 262143
    assert all(len(r['excerpt']) <= 512 for r in rows)
    assert rows[-1]['truncated_before'] and not rows[-1]['truncated_after']


@pytest.mark.parametrize('query', ['a', 'absent'], ids=['dense-hits','no-hits'])
def test_fixed_checkpoint_interval_also_covers_dense_hits_and_no_hits(query):
    text = 'a' * (occurrences.SCAN_CHARS*3+1)
    calls=[]
    scan(text, query, checkpoint=lambda: calls.append(1))
    assert len(calls)==5  # Four chunks and the final completion check.


@pytest.mark.parametrize('query', ['a', 'absent'], ids=['dense-hits','no-hits'])
def test_cancel_during_full_scan_even_after_page_is_full(query):
    calls=[]
    def cancel():
        calls.append(1)
        if len(calls)==2:raise CoreError('CANCELLED','cancelled')
    with pytest.raises(CoreError, match='cancelled') as error:
        scan('a'*(occurrences.SCAN_CHARS*3),query,checkpoint=cancel)
    assert error.value.code=='CANCELLED' and len(calls)==2


@pytest.mark.parametrize('control', ['\0','\x01','\x08','\x0b','\x0c','\x1f'], ids=['nul','soh','backspace','vertical-tab','form-feed','unit-separator'])
def test_late_controls_reject_even_after_page_filled_or_zero_matches(control):
    for query in ['a','absent']:
        with pytest.raises(CoreError) as error:scan('a'*1000+control,query)
        assert error.value.code=='SOURCE_ENCODING_UNSUPPORTED'


@pytest.mark.parametrize('offset', [True,False,-200,1,199,201,262001,262200,262144,1.0,None,'200'], ids=['true','false','negative','one','unaligned-before','unaligned-after','upper-unaligned','upper-aligned','byte-limit','float','null','string'])
def test_invalid_page_offsets(offset):
    with pytest.raises(CoreError) as error:occurrences.validate_occurrence_offset(offset)
    assert error.value.code=='INVALID_QUERY_OPTIONS'


@pytest.mark.parametrize('offset', [0,200,262000], ids=['first','second','last-possible'])
def test_valid_page_offsets(offset):
    occurrences.validate_occurrence_offset(offset)


def reference(path='Modules/code.bsl'):
    return {'input_sha256':'a'*64,'relative_path':path,'raw_sha256':'b'*64}


@pytest.mark.parametrize('path', ['../code.bsl','/code.bsl','x/../code.bsl','code.xml','code.bsl/','x\\code.bsl','code\x00.bsl','\ud800.bsl',None,123,'x'*1025+'.bsl'], ids=['traversal','absolute','embedded-traversal','metadata','trailing-separator','backslash','nul','surrogate','null','number','long-path'])
def test_unsafe_or_nonmodule_reference_is_not_authority(path):
    with pytest.raises(CoreError) as error:occurrences._reference(reference(path),'a'*64)
    assert error.value.code=='SOURCE_NOT_AVAILABLE'


@pytest.mark.parametrize('mutation', [None,{}, {'input_sha256':'c'*64},{'raw_sha256':'B'*64},{'raw_sha256':None},{'extra':1}], ids=['null','empty','archive-mismatch','upper-hash','null-hash','extra-field'])
def test_reference_has_exact_shape_and_expected_hashes(mutation):
    candidate = mutation if mutation in (None,{}) else {**reference(),**mutation}
    with pytest.raises(CoreError) as error:occurrences._reference(candidate,'a'*64)
    assert error.value.code=='SOURCE_NOT_AVAILABLE'


def test_reference_is_copied_and_extension_match_is_case_insensitive():
    original=reference('Modules/code.OS')
    selected=occurrences._reference(original,'a'*64)
    original['raw_sha256']='c'*64
    assert selected['raw_sha256']=='b'*64
