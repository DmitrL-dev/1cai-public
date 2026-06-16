
"""Utilities for rendering security scan reports."""

from __future__ import annotations

from typing import Iterable, Mapping

SEVERITY_LEVELS = {
    "critical": ("🛑", "Critical"),
    "high": ("🚨", "High"),
    "medium": ("⚠️", "Medium"),
    "low": ("ℹ️", "Low"),
}


def _format_severity(value: str | None) -> str:
    if not value:
        return "ℹ️  Unknown"
    icon, title = SEVERITY_LEVELS.get(value.lower(), ("ℹ️", value.capitalize()))
    return f"{icon} {title}"


def generate_markdown_report(payload: Mapping) -> str:
    """Convert JSON payload to Markdown summary."""

    lines: list[str] = []
    run_id = payload.get("run_id", "n/a")
    generated_at = payload.get("generated_at", "n/a")
    profile = payload.get("profile", "n/a")
    results = payload.get("results", []) or []

    lines.append("# Security Scan Report")
    lines.append("")
    lines.append(f"- **Run ID:** `{run_id}`")
    lines.append(f"- **Generated:** `{generated_at}`")
    lines.append(f"- **Profile:** `{profile}`")
    lines.append("")

    if not results:
        lines.append("> ✅ No results recorded.")
        return "\n".join(lines)

    for entry in results:
        target = entry.get("target", "unknown target")
        entry_profile = entry.get("profile", profile)
        findings: Iterable[Mapping] = entry.get("findings", []) or []
        notes: Iterable[str] = entry.get("notes", []) or []

        lines.append(f"## Target: `{target}`")
        lines.append(f"_Profile_: `{entry_profile}`")
        lines.append("")

        if not findings:
            lines.append("> ✅ No findings.")
        else:
            lines.append("| Severity | Title | Description | Evidence |")
            lines.append("| --- | --- | --- | --- |")
            for finding in findings:
                severity = _format_severity(finding.get("severity"))
                title = finding.get("title", "-").replace("|", "\\|")
                description = (finding.get("description") or "-").replace("|", "\\|")
                evidence = (finding.get("evidence") or "-").replace("|", "\\|")
                lines.append(f"| {severity} | **{title}** | {description} | {evidence} |")

        if notes:
            lines.append("")
            lines.append("**Notes:**")
            for note in notes:
                lines.append(f"- {note}")

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def generate_html_report(payload: Mapping) -> str:
    """Convert JSON payload to HTML for dashboards/portal."""

    run_id = payload.get("run_id", "n/a")
    generated_at = payload.get("generated_at", "n/a")
    profile = payload.get("profile", "n/a")
    results = payload.get("results", []) or []

    rows = []
    for entry in results:
        target = entry.get("target", "unknown target")
        entry_profile = entry.get("profile", profile)
        findings: Iterable[Mapping] = entry.get("findings", []) or []
        notes: Iterable[str] = entry.get("notes", []) or []

        if findings:
            table_rows = "".join(
                f"<tr><td>{_format_severity(f.get('severity'))}</td>"
                f"<td>{f.get('title','-')}</td>"
                f"<td>{f.get('description','-')}</td>"
                f"<td>{f.get('evidence','-')}</td></tr>"
                for f in findings
            )
        else:
            table_rows = "<tr><td colspan='4'>✅ Нет проблем</td></tr>"

        note_items = "".join(f"<li>{note}</li>" for note in notes) if notes else ""

        rows.append(
            f"""
            <section>
              <h2>Target: {target}</h2>
              <p><strong>Profile:</strong> {entry_profile}</p>
              <table>
                <thead>
                  <tr><th>Severity</th><th>Title</th><th>Description</th><th>Evidence</th></tr>
                </thead>
                <tbody>
                  {table_rows}
                </tbody>
              </table>
              {'<h3>Notes</h3><ul>' + note_items + '</ul>' if note_items else ''}
            </section>
            """
        )

    body = "\n".join(rows) if rows else "<p>✅ No results recorded.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Security Scan Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.4; padding: 1.5rem; }}
    h1 {{ color: #1f2933; }}
    h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    section {{ margin-bottom: 2rem; }}
  </style>
</head>
<body>
  <h1>Security Scan Report</h1>
  <p><strong>Run ID:</strong> {run_id}</p>
  <p><strong>Generated:</strong> {generated_at}</p>
  <p><strong>Profile:</strong> {profile}</p>
  {body}
</body>
</html>
"""

