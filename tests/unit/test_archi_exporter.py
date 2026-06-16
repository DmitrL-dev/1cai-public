"""
Unit tests for ArchiExporter
"""

import pytest
from unittest.mock import Mock
from src.exporters.archi_exporter import ArchiExporter


class TestArchiExporter:
    """Test ArchiExporter class"""

    @pytest.fixture
    def mock_graph_service(self):
        """Create mock graph service"""
        service = Mock()
        service.execute_query = Mock(return_value=[])
        return service

    @pytest.fixture
    def exporter(self, mock_graph_service):
        """Create ArchiExporter instance"""
        return ArchiExporter(mock_graph_service)

    def test_exporter_initialization(self, exporter, mock_graph_service):
        """Test exporter initializes correctly"""
        assert exporter.graph_service == mock_graph_service

    def test_element_type_mapping(self, exporter):
        """Test element type mapping exists"""
        assert hasattr(ArchiExporter, "ELEMENT_TYPE_MAP")
        assert isinstance(ArchiExporter.ELEMENT_TYPE_MAP, dict)
        assert "Module" in ArchiExporter.ELEMENT_TYPE_MAP
        assert "Function" in ArchiExporter.ELEMENT_TYPE_MAP

    def test_relationship_type_mapping(self, exporter):
        """Test relationship type mapping exists"""
        assert hasattr(ArchiExporter, "RELATIONSHIP_TYPE_MAP")
        assert isinstance(ArchiExporter.RELATIONSHIP_TYPE_MAP, dict)
        assert "DEPENDS_ON" in ArchiExporter.RELATIONSHIP_TYPE_MAP
        assert "CALLS" in ArchiExporter.RELATIONSHIP_TYPE_MAP

    def test_generate_id(self, exporter):
        """Test ID generation"""
        id1 = exporter._generate_id("test")
        id2 = exporter._generate_id("test")

        assert id1.startswith("test_")
        assert id2.startswith("test_")
        assert id1 != id2  # Should be unique

    def test_create_element_with_valid_node(self, exporter):
        """Test element creation with valid node"""
        node = {
            "id": 123,
            "labels": ["Module"],
            "name": "TestModule",
            "description": "Test description",
            "properties": {"version": "1.0"},
        }

        element = exporter._create_element(node)

        assert element is not None
        assert element.tag == "element"
        assert "identifier" in element.attrib

    def test_create_element_without_labels(self, exporter):
        """Test element creation without labels"""
        node = {"id": 123, "labels": [], "name": "TestNode"}

        element = exporter._create_element(node)

        assert element is None

    def test_create_relationship_with_valid_data(self, exporter):
        """Test relationship creation"""
        rel = {"id": 456, "source_id": 123, "target_id": 789, "type": "DEPENDS_ON", "properties": {}}

        element_map = {123: "elem_123", 789: "elem_789"}

        relationship = exporter._create_relationship(rel, element_map)

        assert relationship is not None
        assert relationship.tag == "relationship"
        assert relationship.attrib["source"] == "elem_123"
        assert relationship.attrib["target"] == "elem_789"

    def test_create_relationship_missing_elements(self, exporter):
        """Test relationship creation with missing elements"""
        rel = {"id": 456, "source_id": 999, "target_id": 789, "type": "DEPENDS_ON"}  # Not in element_map

        element_map = {789: "elem_789"}

        relationship = exporter._create_relationship(rel, element_map)

        assert relationship is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
