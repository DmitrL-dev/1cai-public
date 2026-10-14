"""Shared platform matrix helpers for OS-conditional test contracts.

`analysis.bytes.plan` is portable on Windows and Linux and unavailable on
macOS (see docs/product/PORTABLE-CORE.md, docs/product/PLATFORM-SUPPORT.md and
rentgen_core/capabilities.py `_PORTABLE`). Tests must keep parser/pure logic
runnable everywhere, run real CLI execution only on a supported OS, and assert
the documented `CAPABILITY_UNAVAILABLE`-before-IO refusal on every OS.
"""
import sys

import pytest

from rentgen_core import capabilities

# Commands whose capability group is `analysis.bytes.plan`.
BYTES_PLAN_COMMANDS = (
    "metadata-materialize",
    "edt-attribute-plan",
    "edt-inventory-plan",
)
BYTES_PLAN_CAPABILITY = "analysis.bytes.plan"

# Real CLI execution needs a platform the capability matrix actually enables.
# This host is neither a Linux nor a Windows acceptance run.
requires_bytes_plan = pytest.mark.skipif(
    not capabilities.capability_status(BYTES_PLAN_CAPABILITY)["supported"],
    reason=(
        "analysis.bytes.plan CLI execution requires Windows or Linux; "
        f"{sys.platform} only exposes the capability matrix"
    ),
)
