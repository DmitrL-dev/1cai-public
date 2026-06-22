"""
ArchiMate Importer - Import ArchiMate models into Unified Change Graph

Imports ArchiMate XML files with transaction support and rollback.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.modules.graph_api.services.graph_service import GraphService

logger = logging.getLogger(__name__)


class ArchiImporter:
    """Import ArchiMate models into Neo4j with transaction support"""

    # Mapping from ArchiMate element types to Neo4j labels
    ELEMENT_LABEL_MAP = {
        "ApplicationComponent": "Module",
        "application-component": "Module",
        "ApplicationFunction": "Function",
        "application-function": "Function",
        "BusinessProcess": "Process",
        "business-process": "Process",
        "DataObject": "Document",
        "data-object": "Document",
        "ApplicationInterface": "Interface",
        "application-interface": "Interface",
        "ApplicationService": "Service",
        "application-service": "Service",
    }

    # Mapping from ArchiMate relationship types to Neo4j types
    RELATIONSHIP_TYPE_MAP = {
        "Composition": "CONTAINS",
        "composition-relationship": "CONTAINS",
        "Aggregation": "HAS",
        "aggregation-relationship": "HAS",
        "Assignment": "ASSIGNED_TO",
        "assignment-relationship": "ASSIGNED_TO",
        "Realization": "IMPLEMENTS",
        "realization-relationship": "IMPLEMENTS",
        "Serving": "SERVES",
        "serving-relationship": "SERVES",
        "Access": "ACCESSES",
        "access-relationship": "ACCESSES",
        "Flow": "FLOWS_TO",
        "flow-relationship": "FLOWS_TO",
        "Triggering": "TRIGGERS",
        "triggering-relationship": "TRIGGERS",
        "Association": "RELATED_TO",
        "association-relationship": "RELATED_TO",
    }

    def __init__(self, graph_service: GraphService):
        """Initialize importer with graph service"""
        self.graph_service = graph_service

    async def import_from_archimate(self, file_path: str) -> Dict[str, Any]:
        """
        Import ArchiMate XML file with transaction support

        Args:
            file_path: Path to .archimate file

        Returns:
            Statistics about import
        """
        logger.info("Importing ArchiMate from: %s", file_path)

        # Parse XML
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract elements and relationships
        elements = root.findall(".//{*}element")
        relationships = root.findall(".//{*}relationship")

        element_map = {}
        nodes_created = 0
        relationships_created = 0

        # Use transaction for atomicity
        async with self.graph_service.neo4j.driver.session() as session:
            async with session.begin_transaction() as tx:
                try:
                    # Import elements
                    for element in elements:
                        node_id = await self._import_element(element, tx)
                        if node_id:
                            element_map[element.get("identifier")] = node_id
                            nodes_created += 1

                    # Import relationships
                    for relationship in relationships:
                        success = await self._import_relationship(
                            relationship, element_map, tx
                        )
                        if success:
                            relationships_created += 1

                    # Commit transaction
                    await tx.commit()
                    logger.info(
                        f"Import successful: {nodes_created} nodes, "
                        f"{relationships_created} relationships"
                    )

                except Exception as e:
                    # Rollback on error
                    await tx.rollback()
                    logger.error(f"Import failed, rolled back: {e}", exc_info=True)
                    raise

        return {
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
        }

    async def _import_element(self, element: ET.Element, tx) -> Optional[str]:
        """Import single element with transaction"""
        element_type = element.get("{*}type", "").split(":")[-1]
        label = self.ELEMENT_LABEL_MAP.get(element_type, "ArchiMateElement")

        properties = {
            "name": element.get("name", "Unnamed"),
            "archimate_type": element_type,
            "archimate_id": element.get("identifier"),
        }

        # Add documentation if present
        doc = element.find(".//{*}documentation")
        if doc is not None and doc.text:
            properties["description"] = doc.text

        # Create node
        query = f"""
        CREATE (n:{label} $properties)
        RETURN id(n) as node_id
        """

        result = await tx.run(query, properties=properties)
        record = await result.single()
        return record["node_id"] if record else None

    async def _import_relationship(
        self,
        relationship: ET.Element,
        element_map: Dict[str, str],
        tx,
    ) -> bool:
        """Import single relationship with transaction"""
        rel_type = relationship.get("{*}type", "").split(":")[-1]
        neo4j_type = self.RELATIONSHIP_TYPE_MAP.get(rel_type, "ARCHIMATE_RELATION")

        source_id = element_map.get(relationship.get("source"))
        target_id = element_map.get(relationship.get("target"))

        if not source_id or not target_id:
            logger.warning(f"Skipping relationship: missing source or target")
            return False

        # Create relationship
        query = f"""
        MATCH (a), (b)
        WHERE id(a) = $source_id AND id(b) = $target_id
        CREATE (a)-[r:{neo4j_type}]->(b)
        RETURN r
        """

        result = await tx.run(query, source_id=source_id, target_id=target_id)
        record = await result.single()
        return record is not None


# Example usage
if __name__ == "__main__":
    try:
        from src.db.neo4j_client import Neo4jClient
    except ImportError:
        print("Neo4j client not available (removed from stack)")
        raise SystemExit(1)

    neo4j_client = Neo4jClient()
    neo4j_client.connect()
    graph_service = GraphService(neo4j_client)
    importer = ArchiImporter(graph_service)

    import asyncio

    asyncio.run(importer.import_from_archimate("exports/archi/test.archimate"))
