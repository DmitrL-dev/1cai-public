"""
Unit tests for ArchiImporter
"""

import pytest
from unittest.mock import Mock
from src.exporters.archi_importer import ArchiImporter


class TestArchiImporter:
    """Test ArchiImporter class"""

    @pytest.fixture
    def mock_graph_service(self):
        """Create mock graph service"""
        service = Mock()
        service.execute_query = Mock(return_value=[{"node_id": 123}])
        return service

    @pytest.fixture
    def importer(self, mock_graph_service):
        """Create ArchiImporter instance"""
        return ArchiImporter(mock_graph_service)

    def test_importer_initialization(self, importer, mock_graph_service):
        """Test importer initializes correctly"""
        assert importer.graph_service == mock_graph_service

    def test_element_label_mapping(self, importer):
        """Test element label mapping exists"""
        assert hasattr(ArchiImporter, "ELEMENT_LABEL_MAP")
        assert isinstance(ArchiImporter.ELEMENT_LABEL_MAP, dict)
        assert "application-component" in ArchiImporter.ELEMENT_LABEL_MAP
        assert "application-function" in ArchiImporter.ELEMENT_LABEL_MAP

    def test_relationship_type_mapping(self, importer):
        """Test relationship type mapping exists"""
        assert hasattr(ArchiImporter, "RELATIONSHIP_TYPE_MAP")
        assert isinstance(ArchiImporter.RELATIONSHIP_TYPE_MAP, dict)
        assert "serving-relationship" in ArchiImporter.RELATIONSHIP_TYPE_MAP
        assert "triggering-relationship" in ArchiImporter.RELATIONSHIP_TYPE_MAP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
