"""
Integration test for full data migration
"""

import json
from pathlib import Path

import pytest

# These tests require running databases


@pytest.mark.integration
class TestFullMigration:
    """Test complete migration pipeline"""

    @pytest.mark.skipif(
        not Path("knowledge_base/do.json").exists(), reason="DO configuration not found"
    )
    def test_json_to_postgres_migration(self, test_config):
        """Test JSON to PostgreSQL migration"""
        # This would test the actual migration script
        # Requires running PostgreSQL

        from src.db.postgres_saver import PostgreSQLSaver

        # Connect
        saver = PostgreSQLSaver(**test_config["postgres"])
        if not saver.connect():
            pytest.skip("PostgreSQL not available")

        # Load JSON
        with open("knowledge_base/do.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # Save configuration
        config_id = saver.save_configuration(
            {"name": "DO_TEST", "full_name": "Документооборот (тест)"}
        )

        assert config_id is not None

        # Get stats
        stats = saver.get_statistics("DO_TEST")
        assert stats["configurations"] >= 1

        # Cleanup
        saver.clear_configuration("DO_TEST")
        saver.disconnect()

    @pytest.mark.skipif(True, reason="Requires running Neo4j")  # Skip by default
    def test_postgres_to_neo4j_migration(self, test_config):
        """Test PostgreSQL to Neo4j migration"""
        from src.db.neo4j_client import Neo4jClient

        client = Neo4jClient(**test_config["neo4j"])
        if not client.connect():
            pytest.skip("Neo4j not available")

        # Test creating nodes
        success = client.create_configuration(
            {"name": "TEST", "full_name": "Test Configuration"}
        )

        assert success is True

        # Cleanup
        client.clear_database()
        client.disconnect()
