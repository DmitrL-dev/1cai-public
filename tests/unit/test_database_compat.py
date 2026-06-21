from src import database
from src.infrastructure.db import connection


def test_legacy_database_module_reexports_connection_api():
    assert database.create_pool is connection.create_pool
    assert database.close_pool is connection.close_pool
    assert database.get_pool is connection.get_pool
    assert database.get_db_pool is connection.get_db_pool
    assert database.get_db_connection is connection.get_db_connection
    assert database.check_pool_health is connection.check_pool_health
