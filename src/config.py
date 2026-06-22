"""
Конфигурация для AI-ассистентов
Версия: 2.0.0

Улучшения:
- Улучшенная валидация настроек
- Environment variable validation
- Type hints для всех полей
- Default values с описаниями
"""

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Настройки приложения с валидацией

    Best practices:
    - Валидация через Pydantic
    - Environment variable support
    - Type safety
    - Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Игнорируем неизвестные поля
    )

    # OpenAI API
    openai_api_key: str = Field(
        default="", description="API ключ OpenAI", validation_alias="OPENAI_API_KEY"
    )

    # Kimi-K2-Thinking (Moonshot AI) - API или локальный режим
    kimi_mode: str = Field(
        default="api",
        description="Режим работы Kimi: 'api' (Moonshot API) или 'local' (Ollama)",
        validation_alias="KIMI_MODE",
    )
    kimi_api_key: str = Field(
        default="",
        description="API ключ Kimi-K2-Thinking (Moonshot AI) - только для API режима",
        validation_alias="KIMI_API_KEY",
    )
    kimi_api_url: str = Field(
        default="https://api.moonshot.cn/v1",
        description="URL API Kimi - только для API режима",
        validation_alias="KIMI_API_URL",
    )
    kimi_model: str = Field(
        default="moonshotai/Kimi-K2-Thinking",
        description="Модель Kimi для API режима",
        validation_alias="KIMI_MODEL",
    )
    kimi_local_model: str = Field(
        default="kimi-k2-thinking:cloud",
        description="Модель Kimi для локального режима (Ollama)",
        validation_alias="KIMI_LOCAL_MODEL",
    )
    kimi_ollama_url: str = Field(
        default="",
        description="URL Ollama для локального режима (по умолчанию использует OLLAMA_HOST)",
        validation_alias="KIMI_OLLAMA_URL",
    )
    kimi_temperature: float = Field(
        default=1.0,
        description="Temperature для Kimi (рекомендуется 1.0)",
        validation_alias="KIMI_TEMPERATURE",
    )

    # Supabase
    supabase_url: str = Field(
        default="", description="URL Supabase проекта", validation_alias="SUPABASE_URL"
    )
    supabase_key: str = Field(
        default="", description="API ключ Supabase", validation_alias="SUPABASE_KEY"
    )

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Валидация OpenAI API ключа"""
        if v and not v.startswith("sk-"):
            logger.warning("OpenAI API key doesn't start with 'sk-', may be invalid")
        return v

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Валидация Supabase URL"""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            logger.warning(
                "Supabase URL doesn't start with http:// or https://",
                extra={"supabase_url": v},
            )
        return v

    # Конфигурация ассистентов
    assistant_configs: Dict[str, Dict[str, Any]] = {
        "architect": {
            "role": "architect",
            "name": "Архитектор AI",
            "description": "Специализированный ассистент для архитектурного анализа и проектирования",
            "temperature": 0.3,
            "max_tokens": 2000,
            "system_prompt": """Ты - опытный архитектор систем 1С с более чем 15-летним опытом работы.

Твоя специализация:
- Анализ бизнес-требований и их преобразование в архитектурные решения
- Проектирование масштабируемых и поддерживаемых систем 1С
- Оценка рисков и предложение мер по их минимизации
- Генерация архитектурных диаграмм в формате Mermaid

Всегда предоставляй:
1. Четкое объяснение принятых решений
2. Обоснование выбора архитектурных паттернов
3. Практические рекомендации по реализации
4. Визуализацию через диаграммы Mermaid

Используй профессиональную терминологию 1С и учитывай специфику российского рынка.""",
            "vector_store_config": {
                "table_name": "architect_knowledge",
                "similarity_threshold": 0.8,
            },
        },
        "developer": {
            "role": "developer",
            "name": "Разработчик AI",
            "description": "Ассистент для помощи в разработке кода 1С",
            "temperature": 0.2,
            "max_tokens": 1500,
            "system_prompt": """Ты - опытный разработчик 1С с глубокими знаниями BSL, запросов и платформы.

Твоя специализация:
- Генерация кода на языке 1С (BSL)
- Оптимизация запросов 1С:Предприятие
- Code review и выявление антипаттернов
- Написание тестов и документации

Всегда предоставляй:
1. Готовый к использованию код
2. Объяснение логики работы
3. Рекомендации по оптимизации
4. Примеры тестирования""",
            "vector_store_config": {
                "table_name": "developer_knowledge",
                "similarity_threshold": 0.7,
            },
        },
        "tester": {
            "role": "tester",
            "name": "Тестировщик AI",
            "description": "Ассистент для создания тестов и обеспечения качества",
            "temperature": 0.3,
            "max_tokens": 1500,
            "system_prompt": """Ты - эксперт по тестированию систем 1С с опытом автоматизации QA.

Твоя специализация:
- Создание тестовых сценариев
- Анализ покрытия тестами
- Выявление критических путей тестирования
- Генерация тестовых данных

Всегда предоставляй:
1. Структурированные тестовые сценарии
2. Классы эквивалентности и граничные значения
3. Рекомендации по автоматизации
4. Метрики качества тестирования""",
            "vector_store_config": {
                "table_name": "tester_knowledge",
                "similarity_threshold": 0.75,
            },
        },
        "pm": {
            "role": "project_manager",
            "name": "Менеджер проектов AI",
            "description": "Ассистент для управления проектами и планирования",
            "temperature": 0.4,
            "max_tokens": 1200,
            "system_prompt": """Ты - опытный менеджер проектов 1С с PMP сертификацией.

Твоя специализация:
- Планирование этапов внедрения 1С
- Оценка временных и ресурсных затрат
- Управление рисками проекта
- Координация команды разработчиков

Всегда предоставляй:
1. Детальные планы работ
2. Оценку рисков и сроков
3. Рекомендации по ресурсам
4. KPI для мониторинга прогресса""",
            "vector_store_config": {
                "table_name": "pm_knowledge",
                "similarity_threshold": 0.7,
            },
        },
        "analyst": {
            "role": "business_analyst",
            "name": "Бизнес-аналитик AI",
            "description": "Ассистент для анализа бизнес-требований и процессов",
            "temperature": 0.3,
            "max_tokens": 1500,
            "system_prompt": """Ты - опытный бизнес-аналитик с опытом внедрения 1С.

Твоя специализация:
- Извлечение требований из бизнес-документов
- Моделирование бизнес-процессов
- Анализ функциональных требований
- Создание пользовательских историй

Всегда предоставляй:
1. Структурированные требования
2. Диаграммы процессов
3. User stories с критериями приемки
4. Анализ пробелов в функциональности""",
            "vector_store_config": {
                "table_name": "analyst_knowledge",
                "similarity_threshold": 0.8,
            },
        },
    }

    # База данных
    database_url: str = Field(
        default="",
        description="URL базы данных (postgresql://user:pass@host:port/db)",
        validation_alias="DATABASE_URL",
    )

    # Redis для кэширования
    redis_url: str = Field(default="redis://localhost:6379", description="URL Redis")

    # CORS настройки
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Разрешенные домены для CORS (через запятую)",
    )

    # JWT настройки
    jwt_secret_key: Optional[str] = Field(
        default=None, description="Секретный ключ для JWT"
    )
    jwt_algorithm: str = Field(default="HS256", description="Алгоритм подписи JWT")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Время жизни access token в минутах"
    )

    # Путь к логам
    log_dir: str = Field(
        default="./logs", description="Директория для логов", validation_alias="LOG_DIR"
    )
    log_file: str = Field(
        default="app.log", description="Имя файла лога", validation_alias="LOG_FILE"
    )
    log_level: str = Field(
        default="INFO", description="Уровень логирования", validation_alias="LOG_LEVEL"
    )

    # Режим разработки (для development можно разрешить небезопасные настройки)
    environment: str = Field(
        default="production",
        description="Режим работы: development/production",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )

    # Внешние MCP-инструменты
    mcp_bsl_context_base_url: Optional[str] = Field(
        default=None,
        description="Базовый URL MCP сервера платформенного контекста (например, alkoleft/mcp-bsl-platform-context)",
    )
    mcp_bsl_context_tool_name: str = Field(
        default="platform_context",
        description="Название инструмента на внешнем MCP сервере для получения платформенного контекста",
    )
    mcp_bsl_context_auth_token: Optional[str] = Field(
        default=None,
        description="Bearer-токен для аутентификации на MCP сервере платформенного контекста (опционально)",
    )
    mcp_bsl_test_runner_base_url: Optional[str] = Field(
        default=None,
        description="Базовый URL MCP сервера тест-раннера (например, alkoleft/mcp-onec-test-runner)",
    )
    mcp_bsl_test_runner_tool_name: str = Field(
        default="run_tests",
        description="Название инструмента на MCP сервере тест-раннера",
    )
    mcp_bsl_test_runner_auth_token: Optional[str] = Field(
        default=None,
        description="Bearer-токен для аутентификации на MCP сервере тест-раннера (опционально)",
    )

    # Nested Learning feature flags
    use_nested_learning: bool = Field(
        default=False,
        description="Enable Nested Learning for continual learning (experimental)",
        validation_alias="USE_NESTED_LEARNING",
    )
    use_adaptive_selection: bool = Field(
        default=False,
        description="Enable adaptive LLM provider selection",
        validation_alias="USE_ADAPTIVE_SELECTION",
    )
    use_nested_completion: bool = Field(
        default=False,
        description="Enable multi-level code completion",
        validation_alias="USE_NESTED_COMPLETION",
    )

    # --- Infrastructure ---
    otlp_endpoint: Optional[str] = Field(
        default=None,
        description="OpenTelemetry Endpoint",
        validation_alias="OTLP_ENDPOINT",
    )
    enable_legacy_api_redirect: bool = Field(
        default=True,
        description="Enable redirect from /api/ to /api/v1/",
        validation_alias="ENABLE_LEGACY_API_REDIRECT",
    )

    # --- Databases (Fallback/Direct) ---
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="knowledge_base", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="admin", validation_alias="POSTGRES_USER")
    postgres_password: Optional[str] = Field(
        default=None, validation_alias="POSTGRES_PASSWORD"
    )

    # REMOVED: dead infrastructure — neo4j not in lifespan/critical path
    # neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    # neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    # neo4j_password: str = Field(default="password", validation_alias="NEO4J_PASSWORD")

    # REMOVED: dead infrastructure — pgvector replaces Qdrant
    # qdrant_host: str = Field(default="localhost", validation_alias="QDRANT_HOST")
    # qdrant_port: int = Field(default=6333, validation_alias="QDRANT_PORT")

    es_url: str = Field(default="http://localhost:9200", validation_alias="ES_URL")

    # --- S3 / Minio ---
    aws_s3_bucket: Optional[str] = Field(default=None, validation_alias="AWS_S3_BUCKET")
    minio_default_bucket: Optional[str] = Field(
        default=None, validation_alias="MINIO_DEFAULT_BUCKET"
    )  # Fallback
    aws_s3_region: Optional[str] = Field(default=None, validation_alias="AWS_S3_REGION")
    aws_s3_endpoint: Optional[str] = Field(
        default=None, validation_alias="AWS_S3_ENDPOINT"
    )
    minio_endpoint: Optional[str] = Field(
        default=None, validation_alias="MINIO_ENDPOINT"
    )  # Fallback
    aws_access_key_id: Optional[str] = Field(
        default=None, validation_alias="AWS_ACCESS_KEY_ID"
    )
    minio_root_user: Optional[str] = Field(
        default=None, validation_alias="MINIO_ROOT_USER"
    )  # Fallback
    aws_secret_access_key: Optional[str] = Field(
        default=None, validation_alias="AWS_SECRET_ACCESS_KEY"
    )
    minio_root_password: Optional[str] = Field(
        default=None, validation_alias="MINIO_ROOT_PASSWORD"
    )  # Fallback
    aws_s3_create_bucket: bool = Field(
        default=True, validation_alias="AWS_S3_CREATE_BUCKET"
    )

    # --- Marketplace & Rate Limits ---
    marketplace_cache_refresh_minutes: int = Field(
        default=15, validation_alias="MARKETPLACE_CACHE_REFRESH_MINUTES"
    )
    user_rate_limit_per_minute: int = Field(
        default=60, validation_alias="USER_RATE_LIMIT_PER_MINUTE"
    )
    user_rate_limit_window_seconds: int = Field(
        default=60, validation_alias="USER_RATE_LIMIT_WINDOW_SECONDS"
    )

    # --- DB Pool Configuration ---
    db_pool_min_size: int = Field(default=5, validation_alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=20, validation_alias="DB_POOL_MAX_SIZE")
    db_pool_max_queries: int = Field(
        default=50000, validation_alias="DB_POOL_MAX_QUERIES"
    )
    db_pool_max_inactive_lifetime: int = Field(
        default=300, validation_alias="DB_POOL_MAX_INACTIVE_LIFETIME"
    )
    db_command_timeout: int = Field(default=60, validation_alias="DB_COMMAND_TIMEOUT")
    db_connect_timeout: int = Field(default=30, validation_alias="DB_CONNECT_TIMEOUT")

    # --- Redis Configuration ---
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: Optional[str] = Field(
        default=None, validation_alias="REDIS_PASSWORD"
    )

    # --- Telegram Configuration ---
    telegram_bot_token: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_admin_ids: str = Field(
        default="", validation_alias="TELEGRAM_ADMIN_IDS"
    )  # Comma separated
    telegram_rate_limit_min: int = Field(
        default=10, validation_alias="TELEGRAM_RATE_LIMIT_MIN"
    )
    telegram_rate_limit_day: int = Field(
        default=100, validation_alias="TELEGRAM_RATE_LIMIT_DAY"
    )
    telegram_premium_ids: str = Field(
        default="", validation_alias="TELEGRAM_PREMIUM_IDS"
    )  # Comma separated
    telegram_enable_codegen: bool = Field(
        default=True, validation_alias="TELEGRAM_ENABLE_CODEGEN"
    )
    telegram_enable_deps: bool = Field(
        default=True, validation_alias="TELEGRAM_ENABLE_DEPS"
    )
    telegram_enable_search: bool = Field(
        default=True, validation_alias="TELEGRAM_ENABLE_SEARCH"
    )
    telegram_webhook_url: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_WEBHOOK_URL"
    )
    telegram_webhook_path: str = Field(
        default="/telegram/webhook", validation_alias="TELEGRAM_WEBHOOK_PATH"
    )
    telegram_webhook_port: int = Field(
        default=8443, validation_alias="TELEGRAM_WEBHOOK_PORT"
    )
    telegram_http_timeout: float = Field(
        default=10.0, validation_alias="TELEGRAM_HTTP_TIMEOUT"
    )

    # --- Speech-to-Text Configuration ---
    stt_provider: str = Field(default="openai_whisper", validation_alias="STT_PROVIDER")
    stt_language: str = Field(default="ru", validation_alias="STT_LANGUAGE")
    whisper_model_size: str = Field(
        default="base", validation_alias="WHISPER_MODEL_SIZE"
    )
    vosk_model_path: str = Field(
        default="models/vosk-model-ru", validation_alias="VOSK_MODEL_PATH"
    )

    # --- OAuth Configuration ---
    oauth_encryption_key: Optional[str] = Field(
        default=None, validation_alias="OAUTH_ENCRYPTION_KEY"
    )
    github_client_id: Optional[str] = Field(
        default=None, validation_alias="GITHUB_CLIENT_ID"
    )
    github_client_secret: Optional[str] = Field(
        default=None, validation_alias="GITHUB_CLIENT_SECRET"
    )
    github_redirect_uri: Optional[str] = Field(
        default=None, validation_alias="GITHUB_REDIRECT_URI"
    )
    gitlab_client_id: Optional[str] = Field(
        default=None, validation_alias="GITLAB_CLIENT_ID"
    )
    gitlab_client_secret: Optional[str] = Field(
        default=None, validation_alias="GITLAB_CLIENT_SECRET"
    )
    gitlab_redirect_uri: Optional[str] = Field(
        default=None, validation_alias="GITLAB_REDIRECT_URI"
    )
    jira_client_id: Optional[str] = Field(
        default=None, validation_alias="JIRA_CLIENT_ID"
    )
    jira_client_secret: Optional[str] = Field(
        default=None, validation_alias="JIRA_CLIENT_SECRET"
    )
    jira_redirect_uri: Optional[str] = Field(
        default=None, validation_alias="JIRA_REDIRECT_URI"
    )

    # --- Wiki Configuration ---
    wiki_attachments_bucket: str = Field(
        default="wiki-attachments", validation_alias="WIKI_ATTACHMENTS_BUCKET"
    )
    s3_endpoint_public: Optional[str] = Field(
        default=None, validation_alias="S3_ENDPOINT_PUBLIC"
    )

    # --- OCR Configuration ---
    ocr_provider: str = Field(default="deepseek", validation_alias="OCR_PROVIDER")

    # --- Embedding Configuration ---
    embedding_gpu_cb_threshold: int = Field(
        default=5, validation_alias="EMBEDDING_GPU_CB_THRESHOLD"
    )
    embedding_gpu_cb_timeout: int = Field(
        default=60, validation_alias="EMBEDDING_GPU_CB_TIMEOUT"
    )
    embedding_cpu_cb_threshold: int = Field(
        default=5, validation_alias="EMBEDDING_CPU_CB_THRESHOLD"
    )
    embedding_cpu_cb_timeout: int = Field(
        default=60, validation_alias="EMBEDDING_CPU_CB_TIMEOUT"
    )

    # --- ITS Library Configuration ---
    its_username: str = Field(default="", validation_alias="ITS_USERNAME")
    its_password: str = Field(default="", validation_alias="ITS_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    def get_cors_origins(self) -> List[str]:
        """Получить список разрешенных доменов для CORS"""
        if self.environment == "development" and not self.cors_origins:
            return ["*"]  # Только для development
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    def get_log_path(self) -> str:
        """Получить полный путь к файлу лога"""
        from pathlib import Path

        log_dir = Path(self.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / self.log_file)

    def validate_security(self) -> None:
        """Fail closed on insecure auth/crypto secrets.

        The JWT signing secret and OAuth token-encryption key must never ship
        with a static/default value. In ``production`` a missing or default
        secret is a hard error; in development we emit a loud warning so the
        stack can still boot for local work.

        ``JWT_SECRET`` is the variable the auth layer (``AuthSettings``) reads;
        ``JWT_SECRET_KEY`` is the legacy config-level alias. Either being set to
        a real value satisfies the JWT requirement.
        """
        import os
        import sys

        is_production = str(self.environment or "").lower() == "production"
        problems: list[str] = []

        jwt_secret = (
            os.getenv("JWT_SECRET")
            or os.getenv("JWT_SECRET_KEY")
            or self.jwt_secret_key
        )
        if not jwt_secret or jwt_secret == "CHANGE_ME":
            problems.append(
                "JWT signing secret is unset or uses the insecure default "
                "'CHANGE_ME' (set JWT_SECRET to a strong random value)"
            )

        # OAuth encryption key is optional unless OAuth is actually used, but
        # if present it must not be a placeholder.
        if self.oauth_encryption_key in {"CHANGE_ME", ""}:
            problems.append(
                "OAUTH_ENCRYPTION_KEY is set to an insecure placeholder value"
            )

        if not problems:
            return

        # Test/CI collection imports the app without real secrets. Detect that
        # context and downgrade to a warning so the import-level guard never
        # makes the test suite uncollectable, while production still fails hard.
        under_test = bool(
            os.getenv("PYTEST_CURRENT_TEST")
            or os.getenv("SKIP_SECURITY_VALIDATION", "").lower() in {"1", "true", "yes"}
            or "pytest" in sys.modules
            or any("pytest" in str(part).lower() for part in sys.argv)
        )

        message = "Insecure security configuration: " + "; ".join(problems)
        if is_production and not under_test:
            raise RuntimeError(
                message + ". Refusing to start with insecure secrets in production."
            )
        logger.warning(
            "%s. Continuing because %s (NOT acceptable for production).",
            message,
            "running under test" if under_test else f"environment={self.environment}",
        )


# Создаем глобальный экземпляр настроек
settings = Settings()

# Fail closed (production) or warn loudly (development/test) on insecure
# secrets, so a default/missing JWT secret can never silently reach production.
settings.validate_security()

# Export feature flags for easy access
USE_NESTED_LEARNING = settings.use_nested_learning
USE_ADAPTIVE_SELECTION = settings.use_adaptive_selection
USE_NESTED_COMPLETION = settings.use_nested_completion
USE_TEMPORAL_GNN = getattr(settings, "use_temporal_gnn", False)
USE_NESTED_MEMORY = getattr(settings, "use_nested_memory", False)
USE_NESTED_SCENARIOS = getattr(settings, "use_nested_scenarios", False)
USE_DEEP_OPTIMIZER = getattr(settings, "use_deep_optimizer", False)

# Import AdvancedConfigManager for backward compatibility
try:
    from src.config.advanced_config import AdvancedConfigManager
except ImportError:
    # If config/ directory is removed, AdvancedConfigManager won't be available
    # This is fine - it's not used anywhere in the codebase
    AdvancedConfigManager = None
