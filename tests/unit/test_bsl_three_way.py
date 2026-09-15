"""Byte-preserving, bounded BSL text merge without parser or filesystem I/O."""

import hashlib
import importlib
import json

import pytest

from rentgen_core.errors import CoreError


BOM = b"\xef\xbb\xbf"
BASE = b"first\nseparator\nlast\n"


def merge(*args, **kwargs):
    core = importlib.import_module("rentgen_core")
    materialize = getattr(core, "materialize_bsl_three_way", None)
    assert callable(materialize), "BSL three-way materializer must be exported"
    return materialize(*args, **kwargs)


def fail(code, *args, reason=None, **kwargs):
    with pytest.raises(CoreError) as caught:
        merge(*args, **kwargs)
    error = caught.value
    assert error.code == "BSL_THREE_WAY_" + code
    assert "candidate" not in error.details
    assert len(json.dumps(error.details)) < 40_000
    if reason:
        assert error.details["reason"] == reason
    return error


@pytest.mark.parametrize(
    "base,current,upstream,expected",
    [
        (b"", b"", b"", b""),
        (BASE, BASE, BASE, BASE),
        (BASE, b"current\n", BASE, b"current\n"),
        (BASE, BASE, b"upstream\n", b"upstream\n"),
        (BASE, b"same\n", b"same\n", b"same\n"),
        (b"", b"insert\n", b"", b"insert\n"),
        (BASE, b"", BASE, b""),
        (BASE, BASE, b"", b""),
        (b"one\n", b"one\r\n", b"one\n", b"one\r\n"),
        (b"one\n", b"one\n", BOM + b"one\n", BOM + b"one\n"),
        (BOM + BASE, BASE, BOM + BASE, BASE),
        (BASE, b"first\nseparator\nlast", BASE, b"first\nseparator\nlast"),
        (BASE, b"one\r\ntwo\n", BASE, b"one\r\ntwo\n"),
        (BASE, b"one\r\n", b"one\r\n", b"one\r\n"),
    ],
)
def test_exact_selection_preserves_branch_bytes(base, current, upstream, expected):
    result = merge(base, current, upstream)
    assert result["candidate"] == expected
    assert type(result["candidate"]) is bytes
    assert result["schema"] == 1
    assert result["scope"] == "bsl-text-v1"
    assert result["status"] == "ready"
    assert result["candidate_digest"] == hashlib.sha256(expected).hexdigest()
    for label, value in (("base", base), ("current", current), ("upstream", upstream)):
        assert result[label + "_digest"] == hashlib.sha256(value).hexdigest()


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("bom", [b"", BOM])
@pytest.mark.parametrize("final_newline", [True, False])
def test_disjoint_edits_preserve_encoding_and_line_endings(newline, bom, final_newline):
    suffix = newline if final_newline else b""

    def raw(first, last):
        return bom + newline.join((first, b"separator", last)) + suffix

    result = merge(
        raw(b"first", b"last"), raw(b"ours", b"last"), raw(b"first", b"theirs")
    )
    assert result["candidate"] == raw(b"ours", b"theirs")
    assert result["counts"]["merged_hunks"] == 2
    assert result["merged_hunks"] == [
        {
            "source": "current",
            "kind": "replace",
            "base_range": [0, 1],
            "current_range": [0, 1],
        },
        {
            "source": "upstream",
            "kind": "replace",
            "base_range": [2, 3],
            "upstream_range": [2, 3],
        },
    ]


@pytest.mark.parametrize(
    "base,current,upstream,expected",
    [
        (b"a\nb\nc\nd\ne\n", b"b\nc\nd\ne\n", b"a\nb\nc\nd\nE\n", b"b\nc\nd\nE\n"),
        (b"a\nb\nc\n", b"x\na\nb\nc\n", b"a\nb\nC\n", b"x\na\nb\nC\n"),
        (b"a\nb\nc\n", b"A\nb\nc\n", b"a\nb\nc\nx\n", b"A\nb\nc\nx\n"),
        (
            BASE,
            b"FIRST\nseparator\nlast\n",
            b"first\nseparator\nlast",
            b"FIRST\nseparator\nlast",
        ),
        (
            b"a\nb\nc\nd\ne\n",
            b"A\nb\nc\nd\nE\n",
            b"A\nb\nC\nd\ne\n",
            b"A\nb\nC\nd\nE\n",
        ),
        (b"a\nb\nc\nd\ne\n", b"b\nc\nd\nE\n", b"b\nC\nd\ne\n", b"b\nC\nd\nE\n"),
    ],
)
def test_non_overlapping_insert_delete_and_shared_replacement(
    base, current, upstream, expected
):
    assert merge(base, current, upstream)["candidate"] == expected


@pytest.mark.parametrize(
    "base,current,upstream",
    [
        (BASE, b"OURS\nseparator\nlast\n", b"THEIRS\nseparator\nlast\n"),
        (BASE, b"separator\nlast\n", b"THEIRS\nseparator\nlast\n"),
        (b"a\nb\nc\nd\n", b"a\nd\n", b"a\nb\nC\nd\n"),
        (BASE, b"ours\n" + BASE, b"theirs\n" + BASE),
        (BASE, b"same\nfirst\nseparator\nOURS\n", b"same\nfirst\nseparator\nlast\n"),
        (BASE, BASE + b"ours\n", BASE + b"theirs\n"),
        (BASE, b"FIRST\nseparator\nlast\n", b"first\nSEPARATOR\nlast\n"),
        (BASE, b"FIRST\nseparator\nlast\n", b"insert\n" + BASE),
        (BASE, b"FIRST\nseparator\nlast\n", b"first\ninsert\nseparator\nlast\n"),
    ],
)
def test_overlapping_or_boundary_edits_fail_closed(base, current, upstream):
    error = fail("CONFLICT", base, current, upstream)
    assert error.details["reason"] in {"overlapping_edits", "same_anchor_insertions"}
    assert len(error.details["hunks"]) <= 256


@pytest.mark.parametrize(
    "base,current,upstream,reason",
    [
        (
            BASE,
            b"FIRST\r\nseparator\nlast\n",
            b"first\nseparator\nLAST\n",
            "mixed_newlines",
        ),
        (
            BASE,
            b"FIRST\r\nseparator\r\nlast\r\n",
            b"first\nseparator\nLAST\n",
            "newline_style_changed",
        ),
        (
            BASE,
            BOM + b"FIRST\nseparator\nlast\n",
            b"first\nseparator\nLAST\n",
            "bom_changed",
        ),
        (
            BASE,
            b"FIRST\rseparator\rlast\r",
            b"first\nseparator\nLAST\n",
            "unsupported_newlines",
        ),
    ],
)
def test_composite_merge_rejects_format_changes(base, current, upstream, reason):
    fail("INVALID", base, current, upstream, reason=reason)


@pytest.mark.parametrize(
    "bad", [b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"one\x00two", b"\xff\xfea\x00"]
)
@pytest.mark.parametrize("position", [0, 1, 2])
def test_every_input_is_validated_even_on_exact_selection(bad, position):
    values = [BASE, BASE, BASE]
    values[position] = bad
    fail("INVALID", *values)


@pytest.mark.parametrize(
    "bad", ["text", bytearray(b"text"), memoryview(b"text"), None, 1]
)
def test_requires_exact_immutable_bytes(bad):
    fail("INVALID", BASE, bad, BASE, reason="bytes_required")


@pytest.mark.parametrize("name", ["max_bytes", "max_lines"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3", None, 2**63])
def test_invalid_limits_fail_before_materialization(name, value):
    fail("LIMIT", BASE, BASE, BASE, reason="invalid_limits", **{name: value})


def test_byte_limit_precedes_decode():
    fail("LIMIT", b"\xff\xff", b"", b"", max_bytes=1, reason="byte_limit")


@pytest.mark.parametrize("position", [0, 1, 2])
def test_byte_limit_bounds_each_input(position):
    values = [b"", b"", b""]
    values[position] = b"xx"
    fail("LIMIT", *values, max_bytes=1, reason="byte_limit")


@pytest.mark.parametrize("raw,limit", [(b"a\nb\n", 1), (b"a\nb", 1), (b"\n\n", 1)])
def test_line_count_limit(raw, limit):
    fail("LIMIT", raw, raw, raw, max_lines=limit, reason="line_limit")


@pytest.mark.parametrize("raw", [b"a", b"a\n", b"a\r\n", b"", BOM])
def test_one_line_limit_does_not_count_phantom_final_line(raw):
    assert merge(raw, raw, raw, max_lines=1)["candidate"] == raw


def test_line_bytes_limit():
    raw = b"x" * (1024 * 1024 + 1)
    fail("LIMIT", raw, raw, raw, reason="line_byte_limit")


def test_combined_candidate_is_bounded():
    fail(
        "LIMIT",
        b"a\nb\nc\n",
        b"AAAA\nb\nc\n",
        b"a\nb\nCCCC\n",
        max_bytes=10,
        reason="candidate_byte_limit",
    )


def test_combined_candidate_line_count_is_bounded():
    fail(
        "LIMIT",
        BASE,
        b"insert\n" + BASE,
        BASE + b"append\n",
        max_lines=4,
        reason="candidate_line_limit",
    )


def test_large_diff_span_fails_closed_before_matching():
    base = b"".join(f"base{i}\n".encode() for i in range(2100))
    current = b"".join(f"ours{i}\n".encode() for i in range(2100))
    upstream = b"".join(f"theirs{i}\n".encode() for i in range(2100))
    fail("LIMIT", base, current, upstream, reason="diff_work_limit")


def test_exact_selection_skips_diff_work_limit():
    base = b"".join(f"base{i}\n".encode() for i in range(2100))
    current = b"".join(f"ours{i}\n".encode() for i in range(2100))
    assert merge(base, current, base)["candidate"] == current


def test_evidence_is_deterministic_bounded_and_payload_free():
    lines = [f"line{i}\n".encode() for i in range(1200)]
    ours, theirs = list(lines), list(lines)
    for i in range(0, 1200, 4):
        ours[i] = b"SECRET_CURRENT\n"
        theirs[i + 2] = b"SECRET_UPSTREAM\n"
    inputs = tuple(map(b"".join, (lines, ours, theirs)))
    first = merge(*inputs)
    assert first == merge(*inputs)
    assert len(first["merged_hunks"]) == 256
    assert first["counts"]["merged_hunks"] == 600
    assert first["counts"]["merged_hunks_omitted"] == 344
    assert (
        b"SECRET"
        not in json.dumps({k: v for k, v in first.items() if k != "candidate"}).encode()
    )


def test_errors_do_not_leak_sensitive_lines():
    error = fail(
        "CONFLICT",
        BASE,
        b"SECRET_ONE\nseparator\nlast\n",
        b"SECRET_TWO\nseparator\nlast\n",
    )
    assert "SECRET" not in json.dumps(error.to_dict("request"))
    assert "SECRET" not in str(error)


def test_bytes_inputs_are_not_mutated():
    values = (BASE, b"FIRST\nseparator\nlast\n", b"first\nseparator\nLAST\n")
    before = tuple(hashlib.sha256(value).hexdigest() for value in values)
    merge(*values)
    assert before == tuple(hashlib.sha256(value).hexdigest() for value in values)


def test_utf8_non_ascii_and_non_newline_separators_are_preserved():
    base = "Начало\u2028строки\nразделитель\nКонец\n".encode()
    ours = base.replace("Начало".encode(), "Старт".encode())
    theirs = base.replace("Конец".encode(), "Финиш".encode())
    assert merge(base, ours, theirs)["candidate"] == ours.replace(
        "Конец".encode(), "Финиш".encode()
    )
