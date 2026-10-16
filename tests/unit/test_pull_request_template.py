"""The PR template keeps the block policy's required sections (RELEASE-POLICY-01)."""
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / ".github/pull_request_template.md"


def test_template_requires_scenario_checks_docs_and_explicit_non_claims():
    text = TEMPLATE.read_text("utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Scenario",
        "## Changes",
        "## Checks actually run",
        "## Instructions and limitations",
        "## Not claimed",
    ]
    assert "Exact source SHA" in text and "squashed" in text
