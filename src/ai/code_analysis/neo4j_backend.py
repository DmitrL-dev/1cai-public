"""
Neo4j Backend for Unified Change Graph
--------------------------------------

Persistent storage implementation for the Code Graph using Neo4j.
"""

from typing import Any, Dict, Iterable, List, Optional

from src.ai.code_analysis.graph import CodeGraphBackend, Edge, EdgeKind, Node, NodeKind

try:
    from src.db.neo4j_client import get_neo4j_client
except ImportError:
    get_neo4j_client = None  # type: ignore


class Neo4jCodeGraphBackend(CodeGraphBackend):
    """
    Persistent Neo4j implementation of the Code Graph Backend.
    """

    def __init__(self) -> None:
        self.client = get_neo4j_client()

    async def upsert_node(self, node: Node) -> None:
        """
        Merge node into Neo4j.
        Uses MERGE to ensure idempotency.
        """
        cypher = """
        MERGE (n:Node {id: $id})
        SET n.kind = $kind,
            n.display_name = $display_name,
            n.labels = $labels,
            n.props = $props,
            n.updated_at = datetime()
        """
        # Add dynamic labels if needed, but for now we store them as a property list
        # and also add the 'kind' as a Neo4j label for easier filtering

        # Note: In a real implementation, we might want to add Neo4j labels dynamically
        # e.g., MERGE (n:Node:Service ...) if kind is SERVICE.
        # For simplicity and safety against injection, we stick to properties mostly,
        # but we can add the Kind as a label safely since it's an Enum.

        # Safe label injection (NodeKind is an Enum)
        kind_label = node.kind.value
        # Sanitize label just in case (alphanumeric only)
        if not kind_label.replace("_", "").isalnum():
            kind_label = "GenericNode"

        cypher = f"""
        MERGE (n:Node:{kind_label} {{id: $id}})
        SET n.kind = $kind,
            n.display_name = $display_name,
            n.labels = $labels,
            n += $props,
            n.updated_at = datetime()
        """

        # We flatten props into the node properties for easier querying,
        # or store them as a JSON string if they are complex.
        # Here we assume props are simple key-values compatible with Neo4j.
        # If props contain nested dicts, Neo4j driver might complain.
        # For robustness, let's serialize complex props if necessary,
        # but for now we assume simple types.

        params = {
            "id": node.id,
            "kind": node.kind.value,
            "display_name": node.display_name,
            "labels": node.labels,
            "props": node.props,
        }

        # Neo4jClient.execute_query is synchronous in the current implementation
        # (it uses session.run which blocks), but we are in an async method.
        # Ideally, Neo4jClient should be async, but for now we wrap it or just call it.
        # Since the interface is async, we should technically await, but if the underlying
        # client is sync, we just block. This is acceptable for this stage.
        self.client.execute_query(cypher, params)

    async def upsert_edge(self, edge: Edge) -> None:
        """
        Merge relationship into Neo4j.
        """
        # Dynamic relationship type is tricky with parameters in Cypher.
        # We must inject it safely. EdgeKind is an Enum.
        edge_type = edge.kind.value
        if not edge_type.replace("_", "").isalnum():
            edge_type = "RELATED_TO"

        cypher = f"""
        MATCH (source:Node {{id: $source_id}})
        MATCH (target:Node {{id: $target_id}})
        MERGE (source)-[r:{edge_type}]->(target)
        SET r += $props,
            r.updated_at = datetime()
        """

        params = {
            "source_id": edge.source,
            "target_id": edge.target,
            "props": edge.props,
        }

        self.client.execute_query(cypher, params)

    async def get_node(self, node_id: str) -> Optional[Node]:
        """Fetch node by ID."""
        cypher = """
        MATCH (n:Node {id: $id})
        RETURN n
        """
        results = self.client.execute_query(cypher, {"id": node_id})
        if not results:
            return None

        record = results[0]["n"]
        # Convert Neo4j Node to our Node dataclass
        # Neo4j Node object behaves like a dict for properties
        props = dict(record)

        # Extract known fields
        kind_str = props.pop("kind", NodeKind.FILE.value)
        display_name = props.pop("display_name", "")
        labels = props.pop("labels", [])
        # Remove internal fields
        props.pop("id", None)
        props.pop("updated_at", None)

        try:
            kind = NodeKind(kind_str)
        except ValueError:
            kind = NodeKind.FILE  # Fallback

        return Node(
            id=node_id, kind=kind, display_name=display_name, labels=labels, props=props
        )

    async def neighbors(
        self, node_id: str, *, kinds: Optional[Iterable[EdgeKind]] = None
    ) -> List[Node]:
        """Fetch neighbors."""

        rel_type_clause = ""
        if kinds:
            # Construct :TYPE1|:TYPE2 string
            safe_kinds = [k.value for k in kinds if k.value.replace("_", "").isalnum()]
            if safe_kinds:
                rel_type_clause = ":" + "|:".join(safe_kinds)

        cypher = f"""
        MATCH (n:Node {{id: $id}})-[r{rel_type_clause}]->(neighbor)
        RETURN neighbor
        """

        results = self.client.execute_query(cypher, {"id": node_id})
        nodes = []
        for res in results:
            record = res["neighbor"]
            props = dict(record)

            nid = props.pop("id")
            kind_str = props.pop("kind", NodeKind.FILE.value)
            display_name = props.pop("display_name", "")
            labels = props.pop("labels", [])
            props.pop("updated_at", None)

            try:
                kind = NodeKind(kind_str)
            except ValueError:
                kind = NodeKind.FILE

            nodes.append(
                Node(
                    id=nid,
                    kind=kind,
                    display_name=display_name,
                    labels=labels,
                    props=props,
                )
            )

        return nodes

    async def find_nodes(
        self,
        *,
        kind: Optional[NodeKind] = None,
        label: Optional[str] = None,
        prop_equals: Optional[Dict[str, Any]] = None,
    ) -> List[Node]:
        """Search nodes."""

        clauses = ["(n:Node)"]
        params = {}

        if kind:
            # Use the label optimization we added in upsert
            # clauses[0] = f"(n:Node:{kind.value})"
            # Or just filter by property
            clauses.append("n.kind = $kind")
            params["kind"] = kind.value

        if label:
            # Check if label is in the labels list
            clauses.append("$label IN n.labels")
            params["label"] = label

        if prop_equals:
            for k, v in prop_equals.items():
                # Parameterize keys to avoid injection if keys are dynamic (unlikely but safe)
                # But Cypher parameters are for values. Keys in WHERE must be static or map lookups.
                # Safe way: n.prop = value
                if k.replace("_", "").isalnum():
                    clauses.append(f"n.{k} = ${k}_val")
                    params[f"{k}_val"] = v

        where_clause = " WHERE " + " AND ".join(clauses[1:]) if len(clauses) > 1 else ""

        cypher = f"""
        MATCH {clauses[0]}
        {where_clause}
        RETURN n
        """

        results = self.client.execute_query(cypher, params)
        nodes = []
        for res in results:
            record = res["n"]
            props = dict(record)

            nid = props.pop("id")
            kind_str = props.pop("kind", NodeKind.FILE.value)
            display_name = props.pop("display_name", "")
            labels = props.pop("labels", [])
            props.pop("updated_at", None)

            try:
                kind = NodeKind(kind_str)
            except ValueError:
                kind = NodeKind.FILE

            nodes.append(
                Node(
                    id=nid,
                    kind=kind,
                    display_name=display_name,
                    labels=labels,
                    props=props,
                )
            )

        return nodes
