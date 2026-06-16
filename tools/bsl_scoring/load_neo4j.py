"""Load BSL scoring results into Neo4j graph database."""

import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.db.neo4j_client import Neo4jClient, get_neo4j_client


def load_scores(scores_path: Path, batch_size: int = 2000) -> dict:
    """Load scores.json into Neo4j BSL_MODULE nodes.

    Returns stats dict with counts.
    """
    # Load scores
    with open(scores_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modules = data.get("modules", data) if isinstance(data, dict) else data
    print(f"Loading {len(modules)} module scores into Neo4j...", file=sys.stderr)

    client = get_neo4j_client()
    if not client.verify_connectivity():
        print("ERROR: Cannot connect to Neo4j", file=sys.stderr)
        return {"error": "connection_failed"}

    # Create index on module_path for fast MERGE
    client.run_write("CREATE INDEX IF NOT EXISTS FOR (n:BSL_MODULE) ON (n.module_path)")

    # Batch upsert
    total = 0
    for i in range(0, len(modules), batch_size):
        batch = modules[i : i + batch_size]
        # Prepare batch records with only needed fields
        records = []
        for m in batch:
            records.append(
                {
                    "module_path": m["module_path"],
                    "module_type": m.get("module_type", "Unknown"),
                    "domain": m.get("domain", "Прочее"),
                    "loc": m.get("loc", 0),
                    "complexity_score": m.get("complexity_score", 0),
                    "documentation_score": m.get("documentation_score", 0),
                    "maintainability_score": m.get("maintainability_score", 0),
                    "code_quality": m.get("code_quality"),
                    "has_n_plus_one": m.get("has_n_plus_one", False),
                    "has_empty_catch": m.get("has_empty_catch", False),
                    "has_deep_nesting": m.get("has_deep_nesting", False),
                }
            )

        client.run_write(
            """
            UNWIND $batch AS s
            MERGE (n:BSL_MODULE {module_path: s.module_path})
            SET n.complexity_score = s.complexity_score,
                n.documentation_score = s.documentation_score,
                n.maintainability_score = s.maintainability_score,
                n.code_quality = s.code_quality,
                n.quality_domain = s.domain,
                n.module_type = s.module_type,
                n.has_n_plus_one = s.has_n_plus_one,
                n.has_empty_catch = s.has_empty_catch,
                n.has_deep_nesting = s.has_deep_nesting,
                n.loc = s.loc
            """,
            {"batch": records},
        )
        total += len(batch)
        print(f"  Progress: {total}/{len(modules)}", file=sys.stderr)

    # Verify
    result = client.run(
        "MATCH (n:BSL_MODULE) WHERE n.complexity_score IS NOT NULL "
        "RETURN count(n) AS scored"
    )
    scored = result[0]["scored"] if result else 0

    stats = {
        "total_loaded": total,
        "verified_scored": scored,
    }

    print(
        f"\nDone. {scored} BSL_MODULE nodes now have quality scores.", file=sys.stderr
    )
    client.close()
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load BSL scores into Neo4j")
    parser.add_argument(
        "--scores", required=True, type=Path, help="Path to scores.json"
    )
    parser.add_argument("--batch-size", type=int, default=2000)
    args = parser.parse_args()
    load_scores(args.scores, args.batch_size)
