
"""
CLI for Business Analyst requirements extraction.

Usage:

    python -m scripts.ba.requirements_cli extract input.docx --document-type tz --output output.json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.ai.agents.business_analyst_agent_extended import \
    BusinessAnalystAgentExtended

app = typer.Typer(add_completion=False)
console = Console()


def _dump(data: dict, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


@app.command()
def extract(
    input: str = typer.Argument(..., help="Путь к документу или текст для анализа"),
    document_type: Optional[str] = typer.Option(None, "-t", "--document-type", help="Тип документа (tz, email, notes)"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Файл для сохранения JSON"),
    no_pretty: bool = typer.Option(False, "--no-pretty", help="Не форматировать JSON вывод"),
):
    """Извлечь требования, user stories и критерии приемки."""
    agent = BusinessAnalystAgentExtended()
    path = Path(input)

    if path.exists():
        result = asyncio.run(agent.extract_requirements_from_file(path, document_type=document_type))
    else:
        doc_type = document_type or "text"
        result = asyncio.run(agent.extract_requirements(input, doc_type))

    rendered = _dump(result, pretty=not no_pretty)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Saved requirements to {output}[/green]")
    else:
        console.print(rendered)


if __name__ == "__main__":
    app()

