"""Reconcile duplicate BSL_MODULE nodes in Neo4j.

Strategy: fetch both sets into Python, match in-memory, batch update via UNWIND.
The Cypher CONTAINS approach times out on 18K×26K cross-product.
"""

import sys

sys.path.insert(0, "C:/1cAI")
from src.db.neo4j_client import get_neo4j_client


def reconcile():
    client = get_neo4j_client()
    if not client.verify_connectivity():
        print("ERROR: Cannot connect to Neo4j", file=sys.stderr)
        return

    # Step 1: Count before
    before = client.run(
        """
        MATCH (n:BSL_MODULE)
        RETURN count(n) AS total,
               sum(CASE WHEN n.complexity_score IS NOT NULL THEN 1 ELSE 0 END) AS scored,
               sum(CASE WHEN n.name IS NOT NULL AND n.complexity_score IS NULL THEN 1 ELSE 0 END) AS callgraph_only,
               sum(CASE WHEN n.module_path IS NOT NULL AND n.name IS NULL THEN 1 ELSE 0 END) AS scoring_only
    """
    )
    print(f"BEFORE: {before[0]}", file=sys.stderr)

    # Step 2: Fetch callgraph nodes (name + metadata_object + module_type)
    cg_nodes = client.run(
        """
        MATCH (n:BSL_MODULE)
        WHERE n.name IS NOT NULL AND n.complexity_score IS NULL AND n.metadata_object IS NOT NULL
        RETURN n.name AS name, n.metadata_object AS meta_obj, n.module_type AS mt
    """
    )
    print(f"  Callgraph nodes to match: {len(cg_nodes)}", file=sys.stderr)

    # Step 3: Fetch scoring nodes (module_path + scores)
    sc_nodes = client.run(
        """
        MATCH (n:BSL_MODULE)
        WHERE n.module_path IS NOT NULL AND n.complexity_score IS NOT NULL AND n.name IS NULL
        RETURN n.module_path AS mp, n.complexity_score AS cx, n.documentation_score AS doc,
               n.maintainability_score AS mi, n.quality_domain AS dom, n.loc AS loc,
               n.has_n_plus_one AS np1, n.has_empty_catch AS ec, n.has_deep_nesting AS dn,
               n.code_quality AS cq
    """
    )
    print(f"  Scoring nodes to match: {len(sc_nodes)}", file=sys.stderr)

    # Step 4: Build scoring index — key = (metadata_object_substring, module_type_suffix)
    # module_path example: "AccountingRegisters/МСФО/Commands/ОтчётМСФО/Ext/CommandModule.bsl"
    # callgraph name example: "МСФО.CommandModule", metadata_object: "МСФО", module_type: "CommandModule"
    # Match: module_path contains metadata_object AND ends with "module_type.bsl"
    sc_by_suffix = {}
    for sc in sc_nodes:
        mp = sc["mp"]
        if not mp:
            continue
        # Extract the suffix (e.g. "CommandModule.bsl") and path segments
        parts = mp.replace("\\", "/").split("/")
        suffix = parts[-1] if parts else ""  # e.g. "CommandModule.bsl"
        mt = suffix.replace(".bsl", "") if suffix.endswith(".bsl") else ""
        if mt not in sc_by_suffix:
            sc_by_suffix[mt] = []
        sc_by_suffix[mt].append(sc)

    # Step 5: Match in Python
    matches = []
    matched_paths = set()
    for cg in cg_nodes:
        mt = cg["mt"]
        meta = cg["meta_obj"]
        if not mt or not meta:
            continue
        candidates = sc_by_suffix.get(mt, [])
        for sc in candidates:
            if meta in sc["mp"]:
                matches.append(
                    {
                        "cg_name": cg["name"],
                        "sc_mp": sc["mp"],
                        "cx": sc["cx"],
                        "doc": sc["doc"],
                        "mi": sc["mi"],
                        "dom": sc["dom"],
                        "loc": sc["loc"],
                        "np1": sc["np1"],
                        "ec": sc["ec"],
                        "dn": sc["dn"],
                        "cq": sc.get("cq"),
                    }
                )
                matched_paths.add(sc["mp"])
                break  # First match wins

    print(f"  Matched: {len(matches)} pairs", file=sys.stderr)

    # Step 6: Batch UNWIND update callgraph nodes
    batch_size = 2000
    for i in range(0, len(matches), batch_size):
        batch = matches[i : i + batch_size]
        client.run_write(
            """
            UNWIND $batch AS m
            MATCH (n:BSL_MODULE {name: m.cg_name})
            SET n.module_path = m.sc_mp,
                n.complexity_score = m.cx,
                n.documentation_score = m.doc,
                n.maintainability_score = m.mi,
                n.quality_domain = m.dom,
                n.loc = m.loc,
                n.has_n_plus_one = m.np1,
                n.has_empty_catch = m.ec,
                n.has_deep_nesting = m.dn,
                n.code_quality = m.cq
        """,
            {"batch": batch},
        )
        print(f"  Updated batch {i}-{i + len(batch)}", file=sys.stderr)

    # Step 7: Delete scoring-only nodes that were merged
    if matched_paths:
        paths_list = list(matched_paths)
        for i in range(0, len(paths_list), 5000):
            chunk = paths_list[i : i + 5000]
            client.run_write(
                """
                UNWIND $paths AS p
                MATCH (n:BSL_MODULE {module_path: p})
                WHERE n.name IS NULL
                DETACH DELETE n
            """,
                {"paths": chunk},
            )
            print(f"  Deleted orphan chunk {i}-{i + len(chunk)}", file=sys.stderr)

    # Step 8: Count after
    after = client.run(
        """
        MATCH (n:BSL_MODULE)
        RETURN count(n) AS total,
               sum(CASE WHEN n.complexity_score IS NOT NULL THEN 1 ELSE 0 END) AS scored,
               sum(CASE WHEN n.name IS NOT NULL THEN 1 ELSE 0 END) AS with_name,
               sum(CASE WHEN n.module_path IS NOT NULL THEN 1 ELSE 0 END) AS with_path
    """
    )
    print(f"AFTER: {after[0]}", file=sys.stderr)

    client.close()
    print("\nReconciliation complete.", file=sys.stderr)


if __name__ == "__main__":
    reconcile()
