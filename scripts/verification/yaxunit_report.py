"""Standalone entry to the same JUnit validator shipped in the core wheel."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rentgen_core.yaxunit_report import parse_report  # noqa: E402, F401
