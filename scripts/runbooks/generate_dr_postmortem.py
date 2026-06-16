
#!/usr/bin/env python3
"""
generate_dr_postmortem.py - Автоматическое создание черновика постмортема после DR rehearsal.

Сценарий:
- Вызывается из workflow `dr-rehearsal.yml` или вручную после `dr_rehearsal_runner.py`.
- Создаёт Markdown-файл на основе `docs/runbooks/postmortem_template.md` в каталоге
  `docs/runbooks/postmortems/DR_<component>_<YYYYMMDD>.md`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "docs" / "runbooks" / "postmortem_template.md"
OUTPUT_DIR = ROOT / "docs" / "runbooks" / "postmortems"


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        return (
            "# DR Rehearsal Postmortem\n\n"
            "> Шаблон postmortem_template.md не найден, используется упрощённый шаблон.\n\n"
        )
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def generate_content(component: str, success: bool) -> str:
    template = load_template()
    now = datetime.now(timezone.utc)
    incident_id = f"DR-{component.upper()}-{now.strftime('%Y%m%d')}"
    status = "SUCCESS (rehearsal)" if success else "PARTIAL / FAILED (rehearsal)"

    header = (
        f"# Postmortem: DR Rehearsal for {component}\n\n"
        f"- Generated at (UTC): {now.isoformat()}\n"
        f"- Component: {component}\n"
        f"- Rehearsal status: {status}\n"
        f"- Suggested Incident ID: {incident_id}\n\n"
        "---\n\n"
    )

    # Простая подстановка, не пытаемся полностью парсить шаблон.
    body = template.replace("**Incident ID:** TODO", f"**Incident ID:** {incident_id}")
    return header + body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate DR rehearsal postmortem draft from template."
    )
    parser.add_argument("component", help="Название компонента (vault/linkerd/finops/...).")
    parser.add_argument(
        "--status",
        choices=["success", "failed"],
        default="success",
        help="Результат rehearsal (по умолчанию success).",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"DR_{args.component}_{date_str}.md"
    target = OUTPUT_DIR / filename

    content = generate_content(args.component, args.status == "success")
    target.write_text(content, encoding="utf-8")
    print(f"[dr-postmortem] created {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()


