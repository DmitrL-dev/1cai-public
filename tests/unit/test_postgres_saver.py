"""
Unit tests for PostgreSQLSaver with Connection Pooling
"""

from unittest.mock import MagicMock, patch

import pytest

from src.db.postgres_saver import PostgreSQLSaver


class TestPostgreSQLSaver:
    """Test PostgreSQL saver functionality with pooling"""

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_connect_success(self, mock_pool_cls):
        """Test successful database connection pool creation"""
        # Setup mock pool
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool

        saver = PostgreSQLSaver(password="test")
        result = saver.connect()

        assert result is True
        assert saver._pool is not None
        mock_pool_cls.assert_called_once()

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_connect_failure(self, mock_pool_cls):
        """Test connection pool failure handling"""
        mock_pool_cls.side_effect = Exception("Connection failed")

        saver = PostgreSQLSaver(password="test")
        result = saver.connect()

        assert result is False
        assert saver._pool is None

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_save_configuration(self, mock_pool_cls, sample_configuration_data):
        """Test saving configuration using pool"""
        # Setup mocks
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Setup pool behavior
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ["test-uuid"]
        mock_pool_cls.return_value = mock_pool

        saver = PostgreSQLSaver(password="test")
        saver.connect()

        config_id = saver.save_configuration(sample_configuration_data)

        assert config_id == "test-uuid"
        assert mock_cursor.execute.called
        assert mock_conn.commit.called
        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_with(mock_conn)

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_save_module(self, mock_pool_cls, sample_module_data):
        """Test saving module using pool"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ["module-uuid"]
        mock_pool_cls.return_value = mock_pool

        saver = PostgreSQLSaver(password="test")
        saver.connect()

        # Mock internal method calls to avoid recursive pool usage issues in test
        # Since save_module calls save_function internally which also tries to get a cursor
        with patch.object(saver, "save_function") as mock_save_func:
            with patch.object(saver, "save_api_usage") as mock_save_api:
                with patch.object(saver, "save_region") as mock_save_region:
                    module_id = saver.save_module("config-id", sample_module_data)

        assert module_id == "module-uuid"
        assert mock_cursor.execute.called
        mock_pool.putconn.assert_called_with(mock_conn)

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_get_statistics(self, mock_pool_cls):
        """Test getting statistics"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (5, 100, 500, 3000, 50000)
        mock_pool_cls.return_value = mock_pool

        saver = PostgreSQLSaver(password="test")
        saver.connect()

        stats = saver.get_statistics()

        assert stats["configurations"] == 5
        assert stats["objects"] == 100
        assert stats["total_lines"] == 50000
        mock_pool.putconn.assert_called_with(mock_conn)

    @patch("psycopg2.pool.ThreadedConnectionPool")
    def test_context_manager(self, mock_pool_cls):
        """Test context manager usage"""
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool

        with PostgreSQLSaver(password="test") as saver:
            assert saver._pool is not None

        # Should close pool on exit
        mock_pool.closeall.assert_called_once()

    @pytest.fixture
    def sample_configuration_data(self):
        return {
            "name": "TestConfig",
            "full_name": "Test Configuration",
            "version": "1.0.0",
            "metadata": {},
        }

    @pytest.fixture
    def sample_module_data(self):
        return {
            "name": "CommonModule",
            "module_type": "CommonModule",
            "code": "Function Test() EndFunction",
            "functions": [],
            "procedures": [],
        }
