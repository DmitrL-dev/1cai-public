"""Keep collected test identities safely bounded on every supported platform.

This repository-wide collection policy includes tests later deselected by -k/-m.
It refuses oversized identities rather than truncating, renaming, or skipping
cases. Large fixtures should use explicit short parametrization IDs instead.
"""
from pathlib import Path

import pytest

MAX_NODE_ID_UTF16_UNITS = 1024


def _node_id_units(nodeid):
    # Windows environment strings use UTF-16; lone surrogates count as one unit.
    return len(nodeid.encode("utf-16-le", errors="surrogatepass")) // 2


def _safe_test_label(item):
    # Never include a parameter ID, payload, or full path in the diagnostic.
    basename = Path(str(item.path)).name
    function = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
    return ascii(basename + "::" + function)[1:-1][:120]


def _validate_node_ids(items):
    oversized = []
    maximum = 0
    for item in items:
        units = _node_id_units(item.nodeid)
        if units > MAX_NODE_ID_UTF16_UNITS:
            maximum = max(maximum, units)
            if len(oversized) < 3:
                oversized.append((_safe_test_label(item), units))
    if oversized:
        examples = "; ".join(f"{label} ({units} UTF-16 units)" for label, units in oversized)
        raise pytest.UsageError(
            f"Collected test node IDs exceed the {MAX_NODE_ID_UTF16_UNITS}-UTF-16-unit limit "
            f"(largest: {maximum}). Examples: {examples}. "
            "Use short explicit ids= values in pytest parametrization. "
            "Collection is refused before test execution; no IDs or cases were changed."
        )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    _validate_node_ids(items)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    # pytest calls this even when modifyitems raised. Refuse again before its
    # terminal reporter can print oversized IDs during --collect-only.
    _validate_node_ids(session.items)
