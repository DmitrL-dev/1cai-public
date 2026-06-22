"""
Конфигурация для модуля аутентификации.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Настройки аутентификации (загружаются из переменных окружения)."""

    jwt_secret: str = Field(default="CHANGE_ME")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
    demo_users: Optional[str] = Field(default=None)
    service_tokens: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
