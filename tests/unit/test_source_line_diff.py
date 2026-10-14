"""Exact reconstruction, deterministic repeated-line ties and bounded refusal."""
from itertools import product
import random
import re

import pytest

from rentgen_core import source_line_diff as diff

EOL = {'LF': '\n', 'CRLF': '\r\n', 'CR': '\r', 'none': ''}


def aligned(before, after, **kwargs):
    result = diff.bounded_line_diff(before, after, **kwargs)
    assert result['status'] == 'complete' and result['reason'] is None
    for side, raw in [('before', before), ('after', after)]:
        selected = [row for row in result['rows'] if row[side + '_line'] is not None]
        assert [row[side + '_line'] for row in selected] == list(range(1, len(selected) + 1))
        rebuilt = ''.join(row['text'] + EOL[row['eol']] for row in selected).encode('utf-8')
        if result[side]['bom']:
            rebuilt = b'\xef\xbb\xbf' + rebuilt
        assert rebuilt == (raw or b'')
    for row in result['rows']:
        assert row['kind'] in ('equal', 'insert', 'delete')
        assert (row['before_line'] is None) == (row['kind'] == 'insert')
        assert (row['after_line'] is None) == (row['kind'] == 'delete')
    return result


def test_exact_line_numbers_and_deletion_first_tie():
    result = aligned(b'a\nb\n', b'b\na\n')
    assert result['rows'] == [
        {'kind': 'delete', 'before_line': 1, 'after_line': None, 'text': 'a', 'eol': 'LF'},
        {'kind': 'equal', 'before_line': 2, 'after_line': 1, 'text': 'b', 'eol': 'LF'},
        {'kind': 'insert', 'before_line': None, 'after_line': 2, 'text': 'a', 'eol': 'LF'},
    ]


@pytest.mark.parametrize('before,after', list(product([None, b'', b'\xef\xbb\xbf', b'\n', b'one'], repeat=2)))
def test_absence_empty_bom_only_and_one_line(before, after):
    result = aligned(before, after)
    for side, raw in [('before', before), ('after', after)]:
        assert result[side]['present'] is (raw is not None)
        assert result[side]['size_bytes'] == (None if raw is None else len(raw))
    if before is None and after == b'':
        assert result['rows'] == []
        assert result['before']['line_count'] is None
        assert result['after']['line_count'] == 0


def test_newline_and_bom_evidence_is_exact_not_normalized():
    raw = b'\xef\xbb\xbf\r\n\n\rfinal'
    result = aligned(raw, b'\r\n\n\rfinal\n')
    assert result['before'] == {'present': True, 'size_bytes': len(raw), 'bom': True,
                                'line_count': 4, 'newlines': {'LF': 1, 'CRLF': 1, 'CR': 1},
                                'final_newline': False}
    assert result['after']['final_newline'] is True
    assert [row['kind'] for row in result['rows']] == ['equal'] * 3 + ['delete', 'insert']
    result = aligned(b'a\r\nb\r', b'a\nb\n')
    assert not any(row['kind'] == 'equal' for row in result['rows'])
    assert aligned(b'\xef\xbb\xbfa', b'a')['rows'][0]['kind'] == 'equal'


def test_unicode_tabs_separators_and_html_remain_literal_data():
    raw = '😀\té e\u0301\u2028a\u2029b\x7f\u0085<script>"&\n'.encode()
    result = aligned(raw, raw)
    assert len(result['rows']) == 1
    assert result['rows'][0]['text'] == raw.decode()[:-1]
    assert [r['kind'] for r in aligned('é'.encode(), 'e\u0301'.encode())['rows']] == ['delete', 'insert']


@pytest.mark.parametrize('raw', [b'\xff', b'\xc0\xaf', b'\xed\xa0\x80', b'a\x00b', b'\x0b', b'\x0c', b'\x1f'])
def test_unsupported_encoding_or_control_is_unavailable_without_partial_rows(raw):
    result = diff.bounded_line_diff(b'prefix\n', raw)
    assert result['status'] == 'unavailable'
    assert result['reason'] == 'SOURCE_ENCODING_UNSUPPORTED' and result['rows'] == []
    assert result['after']['line_count'] is None


def test_byte_limit_counts_bom_and_utf8_bytes():
    aligned(b'a' * diff.SOURCE_BYTES, b'a' * diff.SOURCE_BYTES)
    aligned(b'\xef\xbb\xbf' + b'a' * (diff.SOURCE_BYTES - 3), b'')
    for raw in [b'a' * (diff.SOURCE_BYTES + 1), ('😀' * (diff.SOURCE_BYTES // 4 + 1)).encode()]:
        result = diff.bounded_line_diff(raw, b'')
        assert result['reason'] == 'SOURCE_TOO_LARGE' and result['rows'] == []
        assert result['before']['size_bytes'] == len(raw)
        assert result['before']['bom'] is None


def test_line_limit_includes_blank_lines_and_no_phantom_trailing_line():
    raw = b'\n' * diff.LINES_PER_SIDE
    assert len(aligned(raw, raw)['rows']) == diff.LINES_PER_SIDE
    assert len(aligned(None, raw)['rows']) == diff.LINES_PER_SIDE
    result = diff.bounded_line_diff(raw + b'x', b'')
    assert result['reason'] == 'LINE_LIMIT' and result['rows'] == []
    assert result['before']['line_count'] == diff.LINES_PER_SIDE + 1
    assert result['before']['newlines']['LF'] == diff.LINES_PER_SIDE
    assert result['before']['final_newline'] is False


def test_work_limit_boundary_and_repeated_adversarial_lines():
    # (999+1)^2 cells is admitted; (1000+1)^2 is refused before allocation.
    result = aligned(b'a\n' * 999, b'b\n' * 999)
    assert len(result['rows']) == 1998
    assert [r['kind'] for r in result['rows']] == ['delete'] * 999 + ['insert'] * 999
    for before, after in [(b'a\n' * 1000, b'b\n' * 1000),
                          (b'a\nb\n' * 1000, b'b\na\n' * 1000)]:
        result = diff.bounded_line_diff(before, after)
        assert result['reason'] == 'WORK_LIMIT' and result['rows'] == []


def test_common_prefix_and_suffix_avoid_unnecessary_quadratic_work():
    before = b'p\n' * 2000 + b'old\n' + b's\n' * 2000
    after = b'p\n' * 2000 + b'new\n' + b's\n' * 2000
    result = aligned(before, after)
    assert len(result['rows']) == 4002
    assert [r['kind'] for r in result['rows'][2000:2002]] == ['delete', 'insert']


def test_randomized_exact_reconstruction_and_minimal_lcs_edit_count():
    rng = random.Random(314159)
    choices = ['a\n', 'a\r', 'b\r\n', '\n', '😀\n', '<x>\n']
    for _ in range(250):
        left = [rng.choice(choices) for _ in range(rng.randrange(25))]
        right = [rng.choice(choices) for _ in range(rng.randrange(25))]
        # CR at one generated boundary and LF at the next coalesce.
        # Tokenize the actual joined bytes independently before the oracle.
        left = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)", ''.join(left))
        right = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)", ''.join(right))
        # Independent rolling-row LCS oracle on actual line tokens.
        lengths = [0] * (len(right) + 1)
        for a in left:
            previous = lengths[:]
            for j, b in enumerate(right, 1):
                lengths[j] = previous[j - 1] + 1 if a == b else max(previous[j], lengths[j - 1])
        result = aligned(''.join(left).encode(), ''.join(right).encode())
        equal = sum(row['kind'] == 'equal' for row in result['rows'])
        assert equal == lengths[-1]
        assert len(result['rows']) - equal == len(left) + len(right) - 2 * equal
        assert result == diff.bounded_line_diff(''.join(left).encode(), ''.join(right).encode())


class Stop(Exception):
    pass


def test_checkpoint_exceptions_propagate_in_parse_dp_and_before_disclosure(monkeypatch):
    marker = Stop('cancel, permission revoked, or time budget exceeded')
    calls = 0

    def stop_during_parse():
        nonlocal calls
        calls += 1
        if calls == 8:
            raise marker
    with pytest.raises(Stop) as error:
        diff.bounded_line_diff(b'x' * diff.SOURCE_BYTES, b'', check=stop_during_parse)
    assert error.value is marker

    original_array = diff.array
    allocated = False
    def tracked_array(*args):
        nonlocal allocated
        allocated = True
        return original_array(*args)
    monkeypatch.setattr(diff, 'array', tracked_array)
    def stop_in_dp():
        if allocated:
            raise marker
    with pytest.raises(Stop) as error:
        diff.bounded_line_diff(b'a\n' * 999, b'b\n' * 999, check=stop_in_dp)
    assert error.value is marker

    calls = 0
    def count():
        nonlocal calls
        calls += 1
    diff.bounded_line_diff(b'a', b'b', check=count)
    total, calls = calls, 0
    def stop_final():
        nonlocal calls
        calls += 1
        if calls == total:
            raise marker
    with pytest.raises(Stop) as error:
        diff.bounded_line_diff(b'a', b'b', check=stop_final)
    assert error.value is marker


@pytest.mark.parametrize('raw', ['', bytearray(b'x'), 0, False, memoryview(b'x')])
def test_nonbytes_input_is_not_silently_coerced(raw):
    with pytest.raises(TypeError):
        diff.bounded_line_diff(raw, b'')


def test_prefix_suffix_anchors_take_priority_over_middle_deletion_first_ties():
    result = aligned(b'a\nb\n', b'b\nb\n')
    assert [(r['kind'], r['before_line'], r['after_line']) for r in result['rows']] == [
        ('delete', 1, None), ('insert', None, 1), ('equal', 2, 2)]
    result = aligned(b'p\na\nb\ns\n', b'p\nb\na\ns\n')
    assert [r['kind'] for r in result['rows']] == ['equal', 'delete', 'equal', 'insert', 'equal']
