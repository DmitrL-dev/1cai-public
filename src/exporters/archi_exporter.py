"""
ArchiMate Exporter - Export Unified Change Graph to ArchiMate format

Exports Neo4j graph to ArchiMate 3.1 XML format with parameterized queries.
"""

import uuid
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any, Dict, List

from src.utils.structured_logging import StructuredLogger

# Use TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    from src.modules.graph_api.services.graph_service import GraphService

logger = StructuredLogger(__name__).logger


class ArchiExporter:
    """Export graph to ArchiMate XML format"""

    ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"

    # Mapping from Neo4j labels to ArchiMate element types
    ELEMENT_TYPE_MAP = {
        "Module": "ApplicationComponent",
        "Function": "ApplicationFunction",
        "Process": "BusinessProcess",
        "Document": "DataObject",
        "Interface": "ApplicationInterface",
        "Service": "ApplicationService",
    }

    # Mapping from Neo4j relationship types to ArchiMate
    RELATIONSHIP_TYPE_MAP = {
        "CONTAINS": "Composition",
        "HAS": "Aggregation",
        "ASSIGNED_TO": "Assignment",
        "IMPLEMENTS": "Realization",
        "SERVES": "Serving",
        "ACCESSES": "Access",
        "FLOWS_TO": "Flow",
        "TRIGGERS": "Triggering",
        "RELATED_TO": "Association",
        "DEPENDS_ON": "Association",
        "CALLS": "Flow",
    }

    def __init__(self, graph_service: "GraphService"):
        """Initialize exporter with graph service"""
        self.graph_service = graph_service

    async def export_to_archimate(
        self,
        output_path: str,
        filters: Dict[str, Any] = None,
        max_nodes: int = 1000,
        max_relationships: int = 2000,
    ) -> str:
        """
        Export graph to ArchiMate XML file

        Args:
            output_path: Path to output .archimate file
            filters: Optional filters for nodes/relationships
            max_nodes: Maximum number of nodes to export
            max_relationships: Maximum number of relationships to export

        Returns:
            Path to created file
        """
        logger.info(
            f"Exporting graph to ArchiMate: {output_path}",
            extra={
                "max_nodes": max_nodes,
                "max_relationships": max_relationships,
            },
        )

        # Create root element
        root = ET.Element(
            "model",
            {
                "xmlns": self.ARCHIMATE_NS,
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsi:schemaLocation": (
                    f"{self.ARCHIMATE_NS} " "http://www.opengroup.org/xsd/archimate/3.1/" "archimate3_Diagram.xsd"
                ),
                "identifier": self._generate_id(),
                "version": "5.0.0",
            },
        )

        # Add metadata
        self._add_metadata(root)

        # Add elements
        elements = ET.SubElement(root, "elements")
        nodes = await self._fetch_nodes(filters, max_nodes)
        element_map = {}

        for node in nodes:
            element = self._create_element(node)
            if element is not None:
                elements.append(element)
                element_map[node["id"]] = element.get("identifier")

        # Add relationships
        relationships = ET.SubElement(root, "relationships")
        rels = await self._fetch_relationships(filters, max_relationships)

        for rel in rels:
            relationship = self._create_relationship(rel, element_map)
            if relationship is not None:
                relationships.append(relationship)

        # Add views
        views = ET.SubElement(root, "views")
        self._create_default_view(views, element_map, rels)

        # Write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        logger.info(
            f"Export complete: {len(nodes)} elements, " f"{len(rels)} relationships")
        return output_path

    async def _fetch_nodes(self, filters: Dict[str, Any] = None, limit: int = 1000) -> List[Dict]:
        """Fetch nodes from graph with parameterized query"""
        query = """
        MATCH (n)
        WHERE n.type IS NOT NULL
        RETURN
            id(n) as id,
            labels(n) as labels,
            n.name as name,
            n.type as type,
            n.description as description,
            properties(n) as properties
        LIMIT $limit
        """

        result = await self.graph_service.execute_query(query, {"limit": limit})
        return result

    async def _fetch_relationships(self, filters: Dict[str, Any] = None, limit: int = 2000) -> List[Dict]:
        """Fetch relationships from graph with parameterized query"""
        query = """
        MATCH (a)-[r]->(b)
        RETURN
            id(r) as id,
            id(a) as source_id,
            id(b) as target_id,
            type(r) as type,
            properties(r) as properties
        LIMIT $limit
        """

        result = await self.graph_service.execute_query(query, {"limit": limit})
        return result

    def _generate_id(self) -> str:
        """Generate unique identifier"""
        return f"id-{uuid.uuid4()}"

    def _add_metadata(self, root: ET.Element):
        """Add metadata to model"""
        metadata = ET.SubElement(root, "metadata")
        ET.SubElement(metadata, "schema").text = "ArchiMate 3.1"
        ET.SubElement(metadata, "schemaversion").text = "3.1"

    def _create_element(self, node: Dict) -> ET.Element:
        """Create ArchiMate element from Neo4j node"""
        labels = node.get("labels", [])
        if not labels:
            return None

        # Get ArchiMate type
        label = labels[0]
        archimate_type = self.ELEMENT_TYPE_MAP.get(label, "ApplicationComponent")

        element = ET.Element(
            "element",
            {
                "identifier": self._generate_id(),
                "type": archimate_type,
            },
        )

        # Add name
        name = ET.SubElement(element, "name")
        name.text = node.get("name", "Unnamed")

        # Add documentation
        if node.get("description"):
            doc = ET.SubElement(element, "documentation")
            doc.text = node["description"]

        return element

    def _create_relationship(self, rel: Dict, element_map: Dict[str, str]) -> ET.Element:
        """Create ArchiMate relationship from Neo4j relationship"""
        source_id = element_map.get(rel["source_id"])
        target_id = element_map.get(rel["target_id"])

        if not source_id or not target_id:
            return None

        # Get ArchiMate relationship type
        rel_type = rel.get("type", "Association")
        archimate_type = self.RELATIONSHIP_TYPE_MAP.get(rel_type, "Association")

        relationship = ET.Element(
            "relationship",
            {
                "identifier": self._generate_id(),
                "type": archimate_type,
                "source": source_id,
                "target": target_id,
            },
        )

        return relationship

    def _create_default_view(
        self,
        views: ET.Element,
        element_map: Dict[str, str],
        relationships: List[Dict],
    ):
        """Create a default diagram view"""
        view = ET.SubElement(
            views,
            "diagrams",
            {
                "identifier": self._generate_id(),
            },
        )

        name = ET.SubElement(view, "name")
        name.text = "Default View"

        # Add nodes to view (simplified - just list them)
        for elem_id in element_map.values():
            ET.SubElement(
                view,
                "node",
                {
                    "identifier": self._generate_id(),
                    "elementRef": elem_id,
                    "x": "0",
                    "y": "0",
                    "w": "120",
                    "h": "55",
                },
            )
