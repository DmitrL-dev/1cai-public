"""
PostgreSQL Saver for 1C Configurations
Версия: 2.1.0
Refactored: Implemented Connection Pooling and Thread Safety
"""

import hashlib
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import psycopg2
    from psycopg2 import OperationalError
    from psycopg2.extras import Json
except ImportError:
    raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class PostgreSQLSaver:
    """Saves parsed 1C configurations to PostgreSQL using connection pooling"""

    _pool = None

    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        minconn: int = 1,
        maxconn: int = 10,
    ):
        """Initialize PostgreSQL connection pool

        Supports both DATABASE_URL and individual parameters.
        Priority: DATABASE_URL > individual parameters > environment variables > defaults
        """

        # Try to parse DATABASE_URL first
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(database_url)
                host = host or parsed.hostname or "localhost"
                port = port or parsed.port or 5432
                database = database or parsed.path.lstrip("/") or "knowledge_base"
                user = user or parsed.username or "admin"
                password = password or parsed.password or os.getenv("POSTGRES_PASSWORD")
            except Exception as e:
                logger.warning("Failed to parse DATABASE_URL: %s, using defaults", e)

        # Fallback to individual env variables or defaults
        if not host:
            host = os.getenv("POSTGRES_HOST", "localhost")
        if not port:
            port = int(os.getenv("POSTGRES_PORT", "5432"))
        if not database:
            database = os.getenv("POSTGRES_DB", "knowledge_base")
        if not user:
            user = os.getenv("POSTGRES_USER", "admin")
        if not password:
            password = os.getenv("POSTGRES_PASSWORD")

        # Input validation
        if not isinstance(host, str) or not host:
            host = "localhost"
        if not isinstance(port, int) or port < 1 or port > 65535:
            port = 5432
        if not isinstance(database, str) or not database:
            database = "knowledge_base"
        if not isinstance(user, str) or not user:
            user = "admin"

        if not password:
            raise ValueError(
                "PostgreSQL password not provided (set POSTGRES_PASSWORD or DATABASE_URL)"
            )

        self.conn_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
        self.minconn = minconn
        self.maxconn = maxconn

        logger.debug(
            "PostgreSQLSaver initialized",
            extra={"host": host, "port": port, "database": database, "user": user},
        )

    def connect(self, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize connection pool"""
        if self._pool:
            return True

        for attempt in range(max_retries):
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    self.minconn, self.maxconn, **self.conn_params
                )
                logger.info(
                    f"Connected to PostgreSQL pool at {self.conn_params['host']}",
                    extra={"pool_size": self.maxconn},
                )
                return True
            except OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                else:
                    logger.error("Failed to connect to PostgreSQL pool: %s", e)
                    return False
            except Exception as e:
                logger.error("Unexpected error connecting to PostgreSQL: %s", e)
                return False
        return False

    def disconnect(self):
        """Close connection pool"""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Disconnected from PostgreSQL pool")

    def is_connected(self) -> bool:
        """Check if connection pool is active and can execute queries"""
        if not self._pool:
            return False
        try:
            conn = self._pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return True
            finally:
                self._pool.putconn(conn)
        except Exception as e:
            logger.debug("PostgreSQL health check failed: %s", e)
            return False

    @contextmanager
    def get_cursor(self):
        """Context manager for getting a cursor from the pool"""
        if not self._pool:
            if not self.connect():
                raise OperationalError("Could not connect to database")

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._pool.putconn(conn)

    def save_configuration(self, config_data: Dict[str, Any]) -> Optional[str]:
        """Save configuration to database"""
        try:
            with self.get_cursor() as cur:
                # Check if configuration exists
                cur.execute(
                    "SELECT id FROM configurations WHERE name = %s",
                    (config_data["name"],),
                )
                result = cur.fetchone()

                if result:
                    config_id = result[0]
                    # Update existing
                    cur.execute(
                        """
                        UPDATE configurations
                        SET full_name = %s,
                            version = %s,
                            source_path = %s,
                            metadata = %s,
                            parsed_at = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING id
                    """,
                        (
                            config_data.get("full_name"),
                            config_data.get("version"),
                            config_data.get("source_path"),
                            Json(config_data.get("metadata", {})),
                            datetime.now(),
                            config_id,
                        ),
                    )
                    logger.info(
                        "Updated configuration",
                        extra={"config_name": config_data["name"]},
                    )
                else:
                    # Insert new
                    cur.execute(
                        """
                        INSERT INTO configurations (name, full_name, version, source_path, metadata, parsed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
                        (
                            config_data["name"],
                            config_data.get("full_name"),
                            config_data.get("version"),
                            config_data.get("source_path"),
                            Json(config_data.get("metadata", {})),
                            datetime.now(),
                        ),
                    )
                    config_id = cur.fetchone()[0]
                    logger.info(
                        "Created configuration",
                        extra={"config_name": config_data["name"]},
                    )

                return config_id

        except Exception as e:
            logger.error(
                "Error saving configuration", extra={"error": str(e)}, exc_info=True
            )
            return None

    def save_object(self, config_id: str, object_data: Dict[str, Any]) -> Optional[str]:
        """Save 1C object"""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO objects (
                        configuration_id, object_type, name, synonym, description, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (configuration_id, object_type, name)
                    DO UPDATE SET
                        synonym = EXCLUDED.synonym,
                        description = EXCLUDED.description,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                """,
                    (
                        config_id,
                        object_data["type"],
                        object_data["name"],
                        object_data.get("synonym"),
                        object_data.get("description"),
                        Json(object_data.get("metadata", {})),
                    ),
                )
                return cur.fetchone()[0]
        except Exception as e:
            logger.error("Error saving object", extra={"error": str(e)}, exc_info=True)
            return None

    def save_module(
        self,
        config_id: str,
        module_data: Dict[str, Any],
        object_id: Optional[str] = None,
    ) -> Optional[str]:
        """Save BSL module"""
        try:
            code = module_data.get("code", "")
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            line_count = len(code.split("\n")) if code else 0

            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO modules (
                        configuration_id, object_id, name, module_type,
                        code, code_hash, description, source_file, line_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        config_id,
                        object_id,
                        module_data["name"],
                        module_data.get("module_type"),
                        code,
                        code_hash,
                        module_data.get("description"),
                        module_data.get("source_file"),
                        line_count,
                    ),
                )
                module_id = cur.fetchone()[0]

            # Save children (functions, etc.) - separate transactions/calls to keep it simple or nested
            # Since we are using a pool, we can just call other methods.
            # Note: This will use multiple connections from the pool if we are not careful,
            # but since we exited the context manager above, the connection is returned.
            # Ideally, we should pass the cursor, but for refactoring simplicity we'll keep method signatures.
            # However, `save_function` etc. also use `get_cursor()`.

            for func in module_data.get("functions", []):
                self.save_function(module_id, func)
            for proc in module_data.get("procedures", []):
                self.save_function(module_id, proc)
            for api in module_data.get("api_usage", []):
                self.save_api_usage(module_id, api)
            for region in module_data.get("regions", []):
                self.save_region(module_id, region)

            return module_id

        except Exception as e:
            logger.error("Error saving module", extra={"error": str(e)}, exc_info=True)
            return None

    def save_function(self, module_id: str, func_data: Dict[str, Any]) -> Optional[str]:
        """Save function or procedure"""
        try:
            func_type = func_data.get("type", "Function")
            code = func_data.get("code", "")
            complexity_score = self._calculate_complexity(code)

            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO functions (
                        module_id, name, function_type, is_exported,
                        parameters, return_type, region, description, code,
                        start_line, end_line, complexity_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        module_id,
                        func_data["name"],
                        func_type,
                        func_data.get("exported", False),
                        Json(func_data.get("params", [])),
                        func_data.get("return_type"),
                        func_data.get("region"),
                        func_data.get("comments", ""),
                        code,
                        func_data.get("start_line"),
                        func_data.get("end_line"),
                        complexity_score,
                    ),
                )
                return cur.fetchone()[0]
        except Exception as e:
            logger.error(
                "Error saving function", extra={"error": str(e)}, exc_info=True
            )
            return None

    def save_api_usage(self, module_id: str, api_name: str) -> bool:
        """Save API usage"""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_usage (module_id, api_name, usage_count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (module_id, api_name)
                    DO UPDATE SET usage_count = api_usage.usage_count + 1
                """,
                    (module_id, api_name),
                )
                return True
        except Exception as e:
            logger.error(
                "Error saving API usage", extra={"error": str(e)}, exc_info=True
            )
            return False

    def save_region(self, module_id: str, region_data: Dict[str, Any]) -> Optional[str]:
        """Save code region"""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO regions (
                        module_id, name, start_line, end_line, level
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        module_id,
                        region_data["name"],
                        region_data.get("start_line"),
                        region_data.get("end_line"),
                        region_data.get("level", 0),
                    ),
                )
                return cur.fetchone()[0]
        except Exception as e:
            logger.error("Error saving region", extra={"error": str(e)}, exc_info=True)
            return None

    def _calculate_complexity(self, code: str) -> int:
        if not code:
            return 0
        keywords = [
            "Если",
            "If",
            "Иначе",
            "Else",
            "ИначеЕсли",
            "ElseIf",
            "Пока",
            "While",
            "Для",
            "For",
            "Попытка",
            "Try",
            "Исключение",
            "Except",
            "И",
            "And",
            "Или",
            "Or",
        ]
        complexity = 1
        code_lower = code.lower()
        for keyword in keywords:
            complexity += code_lower.count(keyword.lower())
        return complexity

    def clear_configuration(self, config_name: str) -> bool:
        """Clear all data for a configuration"""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    "SELECT id FROM configurations WHERE name = %s", (config_name,)
                )
                result = cur.fetchone()
                if not result:
                    return True

                config_id = result[0]

                # Delete in correct order
                tables = ["api_usage", "regions", "functions", "modules", "objects"]
                allowed_tables = {
                    "api_usage",
                    "regions",
                    "functions",
                    "modules",
                    "objects",
                }

                for table in tables:
                    if table not in allowed_tables:
                        continue

                    if table == "modules":
                        cur.execute(
                            "DELETE FROM modules WHERE configuration_id = %s",
                            (config_id,),
                        )
                    elif table == "objects":
                        cur.execute(
                            "DELETE FROM objects WHERE configuration_id = %s",
                            (config_id,),
                        )
                    elif table == "api_usage":
                        cur.execute(
                            "DELETE FROM api_usage WHERE module_id IN (SELECT id FROM modules WHERE configuration_id = %s)",
                            (config_id,),
                        )
                    elif table == "regions":
                        cur.execute(
                            "DELETE FROM regions WHERE module_id IN (SELECT id FROM modules WHERE configuration_id = %s)",
                            (config_id,),
                        )
                    elif table == "functions":
                        cur.execute(
                            "DELETE FROM functions WHERE module_id IN (SELECT id FROM modules WHERE configuration_id = %s)",
                            (config_id,),
                        )

                logger.info(
                    "Cleared data for configuration", extra={"config_name": config_name}
                )
                return True
        except Exception as e:
            logger.error(
                "Error clearing configuration", extra={"error": str(e)}, exc_info=True
            )
            return False

    def get_statistics(self, config_name: Optional[str] = None) -> Dict[str, int]:
        """Get parsing statistics"""
        try:
            with self.get_cursor() as cur:
                where_clause = ""
                params = []
                if config_name:
                    where_clause = "WHERE c.name = %s"
                    params = [config_name]

                base_query = """
                    SELECT
                        COUNT(DISTINCT c.id) as configs,
                        COUNT(DISTINCT o.id) as objects,
                        COUNT(DISTINCT m.id) as modules,
                        COUNT(DISTINCT f.id) as functions,
                        SUM(m.line_count) as total_lines
                    FROM configurations c
                    LEFT JOIN objects o ON o.configuration_id = c.id
                    LEFT JOIN modules m ON m.configuration_id = c.id
                    LEFT JOIN functions f ON f.module_id = m.id
                """

                full_query = (
                    base_query + " " + where_clause if where_clause else base_query
                )
                cur.execute(full_query, params)
                result = cur.fetchone()

                return {
                    "configurations": result[0] or 0,
                    "objects": result[1] or 0,
                    "modules": result[2] or 0,
                    "functions": result[3] or 0,
                    "total_lines": result[4] or 0,
                }
        except Exception as e:
            logger.error(
                "Error getting statistics", extra={"error": str(e)}, exc_info=True
            )
            return {}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
