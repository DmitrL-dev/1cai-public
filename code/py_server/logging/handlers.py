
"""
Обработчики структурированного логирования.

Специализированные обработчики для различных целей:
- Мониторинг и метрики
- APM системы
- Брокеры сообщений
- Файлы и консоль
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from .config import logging_config
from .formatter import LogLevel, create_log_structure
from .sanitizers import sanitize_for_logging


class StructuredLogger:
    """Основной структурированный логгер"""

    def __init__(self, name: str, **kwargs):
        self.name = name
        self.logger = structlog.get_logger(name)
        self.sanitizer = kwargs.get("sanitizer", None)
        self.handlers: List["BaseHandler"] = []
        self._setup_handlers(kwargs)

    def _setup_handlers(self, kwargs: Dict[str, Any]):
        """Настройка обработчиков"""

        # Консольный обработчик
        if kwargs.get("console", True):
            self.handlers.append(
                ConsoleHandler(
                    color=kwargs.get("color", logging_config.CONSOLE_COLOR),
                    pretty_print=kwargs.get(
                        "pretty_print", logging_config.PRETTY_PRINT
                    ),
                )
            )

        # Файловый обработчик
        if kwargs.get("file_path"):
            self.handlers.append(
                FileHandler(
                    file_path=kwargs["file_path"],
                    rotation=kwargs.get("rotation", "time"),
                    max_size=kwargs.get("max_size", 100 * 1024 * 1024),  # 100MB
                    backup_count=kwargs.get("backup_count", 5),
                )
            )

        # HTTP обработчик для мониторинга
        if kwargs.get("monitor_endpoint"):
            self.handlers.append(
                MonitorHandler(
                    endpoint=kwargs["monitor_endpoint"],
                    auth=kwargs.get("monitor_auth"),
                    timeout=kwargs.get("timeout", 30),
                )
            )

        # APM обработчик
        if kwargs.get("apm_endpoint"):
            self.handlers.append(
                APMHandler(
                    endpoint=kwargs["apm_endpoint"],
                    service_name=kwargs.get(
                        "service_name", logging_config.SERVICE_NAME
                    ),
                )
            )

    def log(self, level: LogLevel, message: str, **kwargs):
        """Логирование с автоматическим применением обработчиков"""

        # Создание структуры лога
        log_data = create_log_structure(
            level=level, message=message, logger_name=self.name, **kwargs
        )

        # Санитизация данных
        if self.sanitizer:
            log_data = sanitize_for_logging(log_data, self.sanitizer)

        # Логирование через structlog
        log_method = getattr(self.logger, level.value.lower())
        log_method(message, **log_data)

        # Отправка через кастомные обработчики
        for handler in self.handlers:
            try:
                handler.handle(log_data)
            except Exception as e:
                # Избегаем бесконечных циклов логирования ошибок
                print(f"Handler error: {e}")

    def info(self, message: str, **kwargs):
        """INFO уровень логирования"""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING уровень логирования"""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """ERROR уровень логирования"""
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """CRITICAL уровень логирования"""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """DEBUG уровень логирования"""
        self.log(LogLevel.DEBUG, message, **kwargs)


class BaseHandler:
    """Базовый класс для обработчиков логов"""

    def handle(self, log_data: Dict[str, Any]):
        """Обработка данных лога"""
        raise NotImplementedError

    def shutdown(self):
        """Закрытие обработчика"""


class ConsoleHandler(BaseHandler):
    """Обработчик для консольного вывода"""

    def __init__(self, color: bool = True, pretty_print: bool = False):
        self.color = color
        self.pretty_print = pretty_print

    def handle(self, log_data: Dict[str, Any]):
        """Вывод в консоль"""
        try:
            if self.pretty_print:
                output = json.dumps(log_data, indent=2, ensure_ascii=False, default=str)
            else:
                output = json.dumps(
                    log_data, separators=(",", ":"), ensure_ascii=False, default=str
                )

            # Цветной вывод для уровней
            if self.color:
                level = log_data.get("level", "INFO")
                colors = {
                    "DEBUG": "\033[36m",  # Cyan
                    "INFO": "\033[32m",  # Green
                    "WARNING": "\033[33m",  # Yellow
                    "ERROR": "\033[31m",  # Red
                    "CRITICAL": "\033[35m",  # Magenta
                }

                color = colors.get(level, "\033[0m")
                reset_color = "\033[0m"

                print(f"{color}{output}{reset_color}")
            else:
                print(output)

        except Exception as e:
            print(f"Console handler error: {e}")


class FileHandler(BaseHandler):
    """Обработчик для записи в файл"""

    def __init__(
        self,
        file_path: str,
        rotation: str = "time",
        max_size: int = 100 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.file_path = file_path
        self.rotation = rotation
        self.max_size = max_size
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._current_size = 0

        # Создание директории если не существует
        import os

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    def handle(self, log_data: Dict[str, Any]):
        """Запись в файл"""
        with self._lock:
            try:
                # Проверка ротации
                if self.rotation == "size" and self._current_size > self.max_size:
                    self._rotate_file()

                # Создание JSON строки
                log_line = json.dumps(log_data, ensure_ascii=False, default=str) + "\n"

                # Запись в файл
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(log_line)
                    self._current_size += len(log_line.encode("utf-8"))

            except Exception as e:
                print(f"File handler error: {e}")

    def _rotate_file(self):
        """Ротация файла"""
        import os
        import shutil

        # Закрытие текущего файла и переименование
        for i in range(self.backup_count - 1, 0, -1):
            old_path = f"{self.file_path}.{i}"
            new_path = f"{self.file_path}.{i + 1}"

            if os.path.exists(old_path):
                if i == self.backup_count - 1:
                    os.remove(old_path)  # Удаляем самый старый
                else:
                    shutil.move(old_path, new_path)

        # Переименование текущего файла
        if os.path.exists(self.file_path):
            shutil.move(self.file_path, f"{self.file_path}.1")

        self._current_size = 0


class AsyncFileHandler(FileHandler):
    """Асинхронный файловый обработчик"""

    def __init__(self, file_path: str, **kwargs):
        super().__init__(file_path, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.buffer = []
        self.buffer_size = 1000
        self.flush_interval = 10  # секунд
        self._last_flush = time.time()
        self._flush_task = None

    def handle(self, log_data: Dict[str, Any]):
        """Асинхронная запись в файл"""
        self.buffer.append(log_data)

        if len(self.buffer) >= self.buffer_size:
            self._flush_buffer()

        if time.time() - self._last_flush > self.flush_interval:
            self._flush_buffer()

    def _flush_buffer(self):
        """Сброс буфера в файл"""
        if self.buffer:
            buffer_copy = self.buffer.copy()
            self.buffer.clear()

            self.executor.submit(self._write_to_file, buffer_copy)
            self._last_flush = time.time()

    def _write_to_file(self, logs: List[Dict[str, Any]]):
        """Запись в файл в отдельном потоке"""
        try:
            with self._lock:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    for log_data in logs:
                        log_line = (
                            json.dumps(log_data, ensure_ascii=False, default=str) + "\n"
                        )
                        f.write(log_line)
                        self._current_size += len(log_line.encode("utf-8"))

                if self.rotation == "size" and self._current_size > self.max_size:
                    self._rotate_file()

        except Exception as e:
            print(f"Async file handler error: {e}")

    def shutdown(self):
        """Закрытие с сбросом буфера"""
        self._flush_buffer()
        self.executor.shutdown(wait=True)


class MonitorHandler(BaseHandler):
    """Обработчик для системы мониторинга (например, Prometheus)"""

    def __init__(
        self,
        endpoint: str,
        auth: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        batch_size: int = 100,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.batch_size = batch_size
        self.buffer = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.logger = logging.getLogger(__name__)

    def handle(self, log_data: Dict[str, Any]):
        """Отправка метрик в систему мониторинга"""

        # Подготовка метрик для отправки
        metrics = self._extract_metrics(log_data)
        if metrics:
            self.buffer.append(metrics)

            if len(self.buffer) >= self.batch_size:
                self._flush_buffer()

    def _extract_metrics(self, log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Извлечение метрик из лога"""
        metrics = {}

        # Метрики производительности
        if "duration_ms" in log_data:
            metrics["request_duration_ms"] = log_data["duration_ms"]

        # Метрики ошибок
        if log_data.get("level") in ["ERROR", "CRITICAL"]:
            metrics["error_count"] = 1
            metrics["error_code"] = log_data.get("error_code", "UNKNOWN")

        # Метрики HTTP
        if "http_status_code" in log_data:
            metrics["http_status"] = log_data["http_status_code"]

            if log_data["http_status_code"] >= 500:
                metrics["server_error_count"] = 1
            elif log_data["http_status_code"] >= 400:
                metrics["client_error_count"] = 1
            else:
                metrics["success_count"] = 1

        # Бизнес-метрики
        if log_data.get("logger_name") == "business":
            metrics["business_event"] = log_data.get("context", {}).get(
                "event_type", "unknown"
            )

        if metrics:
            metrics.update(
                {
                    "timestamp": log_data.get("timestamp"),
                    "correlation_id": log_data.get("correlation_id"),
                    "service_name": log_data.get("service_name"),
                    "logger_name": log_data.get("logger_name"),
                }
            )

        return metrics if metrics else None

    def _flush_buffer(self):
        """Отправка метрик в систему мониторинга"""
        if not self.buffer:
            return

        batch = self.buffer.copy()
        self.buffer.clear()

        self.executor.submit(self._send_metrics, batch)

    def _send_metrics(self, metrics: List[Dict[str, Any]]):
        """Отправка метрик через HTTP"""
        try:
            # Конвертация в формат Prometheus
            prometheus_metrics = self._convert_to_prometheus(metrics)

            # HTTP запрос
            import requests

            headers = {"Content-Type": "text/plain"}
            if self.auth:
                if "username" in self.auth and "password" in self.auth:
                    auth_tuple = (self.auth["username"], self.auth["password"])
                else:
                    headers["Authorization"] = f"Bearer {self.auth.get('token', '')}"

            response = requests.post(
                f"{self.endpoint}/metrics",
                data=prometheus_metrics.encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                self.logger.error(f"Monitor endpoint returned {response.status_code}")

        except Exception as e:
            self.logger.error(f"Failed to send metrics: {e}")

    def _convert_to_prometheus(self, metrics: List[Dict[str, Any]]) -> str:
        """Конвертация в формат Prometheus"""
        lines = []

        for metric_batch in metrics:
            # Базовые метрики
            if "request_duration_ms" in metric_batch:
                corr_id = metric_batch.get("correlation_id", "")
                svc_name = metric_batch.get("service_name", "")
                dur = metric_batch["request_duration_ms"]
                lines.append(
                    f'log_request_duration_ms correlation_id="{corr_id}",service_name="{svc_name}" {dur}'
                )

            # Счетчики ошибок
            if "error_count" in metric_batch:
                err_code = metric_batch.get("error_code", "UNKNOWN")
                svc_name = metric_batch.get("service_name", "")
                err_count = metric_batch["error_count"]
                lines.append(
                    f'log_error_count_total error_code="{err_code}",service_name="{svc_name}" {err_count}'
                )

            # Счетчики HTTP статусов
            if "http_status" in metric_batch:
                status_group = (
                    "2xx"
                    if metric_batch["http_status"] < 300
                    else "3xx"
                    if metric_batch["http_status"] < 400
                    else "4xx"
                    if metric_batch["http_status"] < 500
                    else "5xx"
                )

                svc_name = metric_batch.get("service_name", "")
                lines.append(
                    f'log_http_requests_total status_group="{status_group}",service_name="{svc_name}" 1'
                )

        return "\n".join(lines)

    def shutdown(self):
        """Закрытие с отправкой оставшихся метрик"""
        self._flush_buffer()
        self.executor.shutdown(wait=True)


class APMHandler(BaseHandler):
    """Обработчик для APM систем (Jaeger, Zipkin, etc.)"""

    def __init__(
        self, endpoint: str, service_name: str, max_spans: int = 1000, timeout: int = 30
    ):
        self.endpoint = endpoint.rstrip("/")
        self.service_name = service_name
        self.max_spans = max_spans
        self.timeout = timeout
        self.spans = []
        self.logger = logging.getLogger(__name__)

    def handle(self, log_data: Dict[str, Any]):
        """Создание span для APM системы"""

        # Проверяем, нужно ли создавать span
        if not self._should_create_span(log_data):
            return

        # Создание span
        span = self._create_span(log_data)
        if span:
            self.spans.append(span)

            if len(self.spans) >= self.max_spans:
                self._flush_spans()

    def _should_create_span(self, log_data: Dict[str, Any]) -> bool:
        """Определение, нужно ли создавать span"""
        # Создаем spans для:
        # - HTTP запросов
        # - Долгих операций (>100ms)
        # - Ошибок
        # - Бизнес-событий

        if log_data.get("http_method"):
            return True

        if log_data.get("duration_ms", 0) > 100:
            return True

        if log_data.get("level") in ["ERROR", "CRITICAL"]:
            return True

        if log_data.get("logger_name") == "business":
            return True

        return False

    def _create_span(self, log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание span для трассировки"""

        span = {
            "traceId": log_data.get("correlation_id"),
            "spanId": log_data.get("request_id"),
            "parentSpanId": None,
            "operationName": self._get_operation_name(log_data),
            "startTime": self._parse_timestamp(log_data.get("timestamp")),
            "duration": log_data.get("duration_ms", 0),
            "serviceName": self.service_name,
            "tags": self._extract_tags(log_data),
            "logs": self._extract_logs(log_data),
        }

        # Добавление parent span
        if log_data.get("context", {}).get("parent_correlation"):
            span["parentSpanId"] = log_data["context"]["parent_correlation"]

        return span

    def _get_operation_name(self, log_data: Dict[str, Any]) -> str:
        """Получение имени операции для span"""

        if log_data.get("http_method"):
            return f"{log_data['http_method']} {log_data.get('target_url', '/')}"

        if log_data.get("logger_name") == "business":
            return log_data.get("context", {}).get("operation", "business_operation")

        if log_data.get("logger_name") == "function":
            return log_data.get("context", {}).get("function", "function_call")

        return log_data.get("logger_name", "operation")

    def _parse_timestamp(self, timestamp: str) -> int:
        """Парсинг timestamp в микросекунды для Jaeger"""
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1_000_000)  # микросекунды
        except:
            return int(time.time() * 1_000_000)

    def _extract_tags(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение тегов для span"""
        tags = {
            "level": log_data.get("level"),
            "logger": log_data.get("logger_name"),
        }

        # HTTP теги
        if log_data.get("http_status_code"):
            tags["http.status_code"] = log_data["http_status_code"]
            tags["http.method"] = log_data.get("http_method", "UNKNOWN")

        # Теги ошибок
        if log_data.get("error_code"):
            tags["error.code"] = log_data["error_code"]
            tags["error"] = True

        # Теги производительности
        if log_data.get("duration_ms"):
            tags["duration_ms"] = log_data["duration_ms"]

        return tags

    def _extract_logs(self, log_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Извлечение логов для span"""
        logs = [
            {
                "timestamp": self._parse_timestamp(log_data.get("timestamp")),
                "fields": [
                    {"key": "message", "value": log_data.get("message")},
                    {"key": "level", "value": log_data.get("level")},
                ],
            }
        ]

        # Добавление stack trace для ошибок
        if log_data.get("stacktrace"):
            logs.append(
                {
                    "timestamp": self._parse_timestamp(log_data.get("timestamp")),
                    "fields": [
                        {"key": "error.object", "value": log_data.get("stacktrace")}
                    ],
                }
            )

        return logs

    def _flush_spans(self):
        """Отправка spans в APM систему"""
        if not self.spans:
            return

        spans = self.spans.copy()
        self.spans.clear()

        self._send_spans(spans)

    def _send_spans(self, spans: List[Dict[str, Any]]):
        """Отправка spans через HTTP"""
        try:
            payload = {
                "spans": spans,
                "process": {
                    "serviceName": self.service_name,
                    "tags": {
                        "environment": "production",  # можно конфигурировать
                        "version": "1.0.0",
                    },
                },
            }

            import requests

            response = requests.post(
                f"{self.endpoint}/api/traces",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )

            if response.status_code not in [200, 202]:
                self.logger.error(f"APM endpoint returned {response.status_code}")

        except Exception as e:
            self.logger.error(f"Failed to send spans: {e}")

    def shutdown(self):
        """Закрытие с отправкой оставшихся spans"""
        self._flush_spans()


class MessageBrokerHandler(BaseHandler):
    """Обработчик для брокеров сообщений (RabbitMQ, Kafka)"""

    def __init__(self, broker_type: str, connection_config: Dict[str, Any]):
        self.broker_type = broker_type.lower()
        self.connection_config = connection_config
        self.connection = None
        self.producer = None
        self.logger = logging.getLogger(__name__)
        self._connect()

    def _connect(self):
        """Подключение к брокеру"""
        try:
            if self.broker_type == "rabbitmq":
                self._connect_rabbitmq()
            elif self.broker_type == "kafka":
                self._connect_kafka()
            else:
                raise ValueError(f"Unsupported broker type: {self.broker_type}")
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.broker_type}: {e}")

    def _connect_rabbitmq(self):
        """Подключение к RabbitMQ"""
        try:
            import pika

            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(**self.connection_config)
            )
            self.producer = self.connection.channel()
            self.producer.queue_declare(queue="logs", durable=True)

        except ImportError:
            raise ImportError("pika package required for RabbitMQ")

    def _connect_kafka(self):
        """Подключение к Kafka"""
        try:
            from kafka import KafkaProducer

            self.producer = KafkaProducer(
                bootstrap_servers=self.connection_config.get(
                    "bootstrap_servers", ["localhost:9092"]
                ),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )

        except ImportError:
            raise ImportError("kafka-python package required for Kafka")

    def handle(self, log_data: Dict[str, Any]):
        """Отправка лога в брокер"""
        try:
            if self.broker_type == "rabbitmq":
                self._send_to_rabbitmq(log_data)
            elif self.broker_type == "kafka":
                self._send_to_kafka(log_data)

        except Exception as e:
            self.logger.error(f"Failed to send log to {self.broker_type}: {e}")

    def _send_to_rabbitmq(self, log_data: Dict[str, Any]):
        """Отправка в RabbitMQ"""
        self.producer.basic_publish(
            exchange="",
            routing_key="logs",
            body=json.dumps(log_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                correlation_id=log_data.get("correlation_id"),
            ),
        )

    def _send_to_kafka(self, log_data: Dict[str, Any]):
        """Отправка в Kafka"""
        self.producer.send(
            "logs",
            value=log_data,
            key=log_data.get("correlation_id", "").encode("utf-8"),
        )

    def shutdown(self):
        """Закрытие подключения"""
        if self.producer:
            self.producer.close()
        if self.connection:
            self.connection.close()


class DatabaseHandler(BaseHandler):
    """Обработчик для записи в базу данных"""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.connection = None
        self.logger = logging.getLogger(__name__)
        self._connect()

    def _connect(self):
        """Подключение к БД"""
        try:
            db_type = self.db_config.get("type", "sqlite").lower()

            if db_type == "sqlite":
                self._connect_sqlite()
            elif db_type == "postgresql":
                self._connect_postgresql()
            else:
                raise ValueError(f"Unsupported database type: {db_type}")

        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")

    def _connect_sqlite(self):
        """Подключение к SQLite"""
        import os
        import sqlite3

        db_path = self.db_config.get("path", "logs.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.connection = sqlite3.connect(db_path)
        self._create_table()

    def _connect_postgresql(self):
        """Подключение к PostgreSQL"""
        try:
            import psycopg2

            self.connection = psycopg2.connect(
                host=self.db_config["host"],
                database=self.db_config["database"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                port=self.db_config.get("port", 5432),
            )
            self._create_table()

        except ImportError:
            raise ImportError("psycopg2 package required for PostgreSQL")

    def _create_table(self):
        """Создание таблицы для логов"""
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                logger_name TEXT,
                correlation_id TEXT,
                user_id TEXT,
                request_id TEXT,
                duration_ms REAL,
                service_name TEXT,
                error_code TEXT,
                error_type TEXT,
                stacktrace TEXT,
                context TEXT,
                http_method TEXT,
                http_status_code INTEGER,
                target_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        self.connection.commit()

    def handle(self, log_data: Dict[str, Any]):
        """Запись лога в БД"""
        try:
            cursor = self.connection.cursor()

            cursor.execute(
                """
                INSERT INTO logs (
                    timestamp, level, message, logger_name, correlation_id,
                    user_id, request_id, duration_ms, service_name,
                    error_code, error_type, stacktrace, context,
                    http_method, http_status_code, target_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log_data.get("timestamp"),
                    log_data.get("level"),
                    log_data.get("message"),
                    log_data.get("logger_name"),
                    log_data.get("correlation_id"),
                    log_data.get("user_id"),
                    log_data.get("request_id"),
                    log_data.get("duration_ms"),
                    log_data.get("service_name"),
                    log_data.get("error_code"),
                    log_data.get("error_type"),
                    log_data.get("stacktrace"),
                    json.dumps(log_data.get("context", {})),
                    log_data.get("http_method"),
                    log_data.get("http_status_code"),
                    log_data.get("target_url"),
                ),
            )

            self.connection.commit()

        except Exception as e:
            self.logger.error(f"Failed to insert log into database: {e}")

    def shutdown(self):
        """Закрытие подключения к БД"""
        if self.connection:
            self.connection.close()


# Создание основных логгеров
def create_application_logger(name: str = "application") -> StructuredLogger:
    """Создание логгера для приложения"""
    return StructuredLogger(
        name=name,
        console=True,
        file_path=f"/var/log/{name}.log",
        monitor_endpoint=logging_config.METRICS_ENDPOINT,
        apm_endpoint=logging_config.APM_ENDPOINT,
    )


def create_http_logger() -> StructuredLogger:
    """Создание логгера для HTTP запросов"""
    return StructuredLogger(
        name="http",
        console=False,
        file_path="/var/log/http_requests.log",
        monitor_endpoint=logging_config.METRICS_ENDPOINT,
        apm_endpoint=logging_config.APM_ENDPOINT,
    )


def create_business_logger() -> StructuredLogger:
    """Создание логгера для бизнес-событий"""
    return StructuredLogger(
        name="business",
        console=True,
        file_path="/var/log/business.log",
        monitor_endpoint=logging_config.METRICS_ENDPOINT,
    )
