
"""Neo4j integration for security findings."""

from __future__ import annotations

from typing import Mapping, Sequence

import httpx


class Neo4jSyncError(RuntimeError):
    """Raised when Neo4j synchronization fails."""


def _build_statements(payload: Mapping) -> tuple[dict, list[dict]]:
    run_id = payload.get("run_id")
    generated_at = payload.get("generated_at")
    profile = payload.get("profile")
    results: Sequence[Mapping] = payload.get("results", []) or []

    findings: list[dict] = []
    idx = 0
    for entry in results:
        target = entry.get("target")
        entry_profile = entry.get("profile", profile)
        notes = entry.get("notes", [])
        for finding in entry.get("findings", []) or []:
            idx += 1
            findings.append(
                {
                    "finding_id": f"{run_id}-{idx}",
                    "target": target,
                    "profile": entry_profile,
                    "severity": finding.get("severity"),
                    "title": finding.get("title"),
                    "description": finding.get("description"),
                    "evidence": finding.get("evidence"),
                    "notes": notes,
                }
            )

    params = {
        "run_id": run_id,
        "generated_at": generated_at,
        "profile": profile,
        "findings": findings,
    }

    statements = [
        {
            "statement": """
            MERGE (run:SecurityRun {run_id: $run_id})
            SET run.generated_at = $generated_at,
                run.profile = $profile
            """,
            "parameters": params,
        }
    ]

    if findings:
        statements.append(
            {
                "statement": """
                UNWIND $findings AS finding
                MERGE (run:SecurityRun {run_id: $run_id})
                MERGE (target:SecurityTarget {name: finding.target})
                MERGE (run)-[:TARGETS]->(target)
                MERGE (f:SecurityFinding {finding_id: finding.finding_id})
                SET f.title = finding.title,
                    f.severity = finding.severity,
                    f.description = finding.description,
                    f.evidence = finding.evidence,
                    f.profile = finding.profile
                MERGE (run)-[:HAS_FINDING]->(f)
                MERGE (f)-[:FOR_TARGET]->(target)
                """,
                "parameters": params,
            }
        )

    return params, statements


def push_results_to_neo4j(
    payload: Mapping,
    *,
    url: str,
    user: str,
    password: str,
    database: str = "neo4j",
) -> None:
    """Send payload to Neo4j transactional endpoint."""

    _, statements = _build_statements(payload)
    if not statements:
        return

    endpoint = f"{url.rstrip('/')}/db/{database}/tx/commit"
    auth = (user, password)
    body = {"statements": statements}

    with httpx.Client(timeout=10.0) as client:
        response = client.post(endpoint, json=body, auth=auth)

    if response.status_code >= 300:
        raise Neo4jSyncError(f"Neo4j responded with {response.status_code}: {response.text}")

    data = response.json()
    if data.get("errors"):
        raise Neo4jSyncError(f"Neo4j reported errors: {data['errors']}")

