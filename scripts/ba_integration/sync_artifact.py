
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.ai.agents.business_analyst_agent_extended import IntegrationConnector


async def sync_artifact(
    artefact: Dict[str, Any],
    targets: Optional[Iterable[str]] = None,
    *,
    connector: Optional[IntegrationConnector] = None,
) -> Dict[str, Any]:
    connector = connector or IntegrationConnector()
    try:
        result = await connector.sync(artefact, list(targets or []))
    finally:
        await connector.aclose()
    return result


def sync_artifact_from_path(path: Path, targets: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    artefact = json.loads(path.read_text(encoding="utf-8"))
    if "type" not in artefact:
        raise ValueError("Artefact JSON must include 'type' field.")
    return asyncio.run(sync_artifact(artefact, targets))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync BA artefacts with external systems.")
    parser.add_argument("artefact", type=Path, help="Path to artefact JSON")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["jira", "confluence"],
        help="Targets to sync (default: jira confluence)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    result = sync_artifact_from_path(args.artefact, args.targets)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()


