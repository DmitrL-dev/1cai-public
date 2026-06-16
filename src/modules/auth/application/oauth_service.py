
"""
Сервис OAuth для модуля аутентификации.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode

import asyncpg
import httpx
from cryptography.fernet import Fernet

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class OAuthService:
    """Сервис для работы с OAuth2 аутентификацией"""

    def __init__(self):
        """Инициализация OAuth сервиса"""
        # Ключ шифрования токенов
        encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY")
        if not encryption_key:
            # Для разработки можно использовать дефолтный ключ, но в проде это ошибка
            logger.warning(
                "OAUTH_ENCRYPTION_KEY не установлен. Используется небезопасный ключ.")
            encryption_key = Fernet.generate_key().decode()

        self.fernet = Fernet(encryption_key.encode())

        # Конфигурация провайдеров
        self.providers = {
            "github": {
                "name": "GitHub",
                "auth_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "user_url": "https://api.github.com/user",
                "client_id": os.getenv("GITHUB_CLIENT_ID"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GITHUB_REDIRECT_URI"),
                "scope": "repo read:user",
            },
            "gitlab": {
                "name": "GitLab",
                "auth_url": "https://gitlab.com/oauth/authorize",
                "token_url": "https://gitlab.com/oauth/token",
                "user_url": "https://gitlab.com/api/v4/user",
                "client_id": os.getenv("GITLAB_CLIENT_ID"),
                "client_secret": os.getenv("GITLAB_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GITLAB_REDIRECT_URI"),
                "scope": "api read_user",
            },
            "jira": {
                "name": "Jira",
                "auth_url": "https://auth.atlassian.com/authorize",
                "token_url": "https://auth.atlassian.com/oauth/token",
                "user_url": "https://api.atlassian.com/me",
                "client_id": os.getenv("JIRA_CLIENT_ID"),
                "client_secret": os.getenv("JIRA_CLIENT_SECRET"),
                "redirect_uri": os.getenv("JIRA_REDIRECT_URI"),
                "scope": "read:jira-work write:jira-work offline_access",
                "audience": "api.atlassian.com",
            },
        }

    async def get_authorization_url(self, provider: str, db: asyncpg.Connection, user_id: int) -> str:
        """Генерирует URL для OAuth авторизации.

        Args:
            provider: Имя провайдера.
            db: Подключение к БД.
            user_id: ID пользователя.

        Returns:
            str: URL для редиректа.

        Raises:
            ValueError: Если провайдер не поддерживается или не настроен.
        """
        if provider not in self.providers:
            raise ValueError(f"Провайдер '{provider}' не поддерживается")

        config = self.providers[provider]

        # Проверить что client_id и client_secret настроены
        if not config["client_id"] or not config["client_secret"]:
            raise ValueError(
                f"OAuth credentials для {provider} не настроены. "
                f"Установите {provider.upper()}_CLIENT_ID и {provider.upper()}_CLIENT_SECRET"
            )

        # Сгенерировать CSRF state
        state = secrets.token_urlsafe(32)
        await self._store_state(db, state, provider, user_id)

        # Построить authorization URL
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": config["scope"],
            "state": state,
            "response_type": "code",
        }

        # Jira требует audience параметр
        if provider == "jira":
            params["audience"] = config["audience"]
            params["prompt"] = "consent"

        url = f"{config['auth_url']}?{urlencode(params)}"

        logger.info("Generated OAuth URL", extra={
                    "provider": provider, "user_id": user_id})
        return url

    async def exchange_code_for_token(self, provider: str, code: str, state: str, db: asyncpg.Connection) -> Dict:
        """Обменивает код авторизации на токен доступа.

        Args:
            provider: Имя провайдера.
            code: Код авторизации.
            state: CSRF токен.
            db: Подключение к БД.

        Returns:
            Dict: Данные токена (provider, user_id, expires_in).

        Raises:
            ValueError: Если провайдер не поддерживается или state невалиден.
        """
        if provider not in self.providers:
            raise ValueError(f"Провайдер '{provider}' не поддерживается")

        # Проверить state (CSRF защита)
        user_id = await self._verify_state(db, state, provider)
        if not user_id:
            raise ValueError("Invalid state parameter")

        config = self.providers[provider]

        # Обменять code на token
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    config["token_url"],
                    data={
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "code": code,
                        "redirect_uri": config["redirect_uri"],
                        "grant_type": "authorization_code",
                    },
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPError as e:
                logger.error("Failed to exchange code for token",
                             extra={"error": str(e)})
                raise

        # Сохранить токены в БД
        await self._store_tokens(db, provider, user_id, token_data)

        logger.info("Successfully exchanged code for token", extra={
                    "provider": provider, "user_id": user_id})

        return {
            "provider": provider,
            "user_id": user_id,
            "expires_in": token_data.get("expires_in", 3600),
        }

    async def refresh_token(self, provider: str, user_id: int, db: asyncpg.Connection) -> Dict:
        """Обновляет access token используя refresh token.

        Args:
            provider: Имя провайдера.
            user_id: ID пользователя.
            db: Подключение к БД.

        Returns:
            Dict: Новые данные токена.

        Raises:
            ValueError: Если провайдер не поддерживается или токен не найден.
        """
        if provider not in self.providers:
            raise ValueError(f"Провайдер '{provider}' не поддерживается")

        config = self.providers[provider]

        # Получить refresh token из БД
        refresh_token = await self._get_refresh_token(db, provider, user_id)
        if not refresh_token:
            raise ValueError(f"Refresh token не найден для {provider}")

        # Обновить токен
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    config["token_url"],
                    data={
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                    headers={"Accept": "application/json"},
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPError as e:
                logger.error("Failed to refresh token", extra={"error": str(e)})
                raise

        # Сохранить новые токены
        await self._store_tokens(db, provider, user_id, token_data)

        logger.info("Successfully refreshed token", extra={
                    "provider": provider, "user_id": user_id})

        return token_data

    async def get_valid_access_token(self, provider: str, user_id: int, db: asyncpg.Connection) -> str:
        """Получает валидный access token, обновляя его при необходимости.

        Args:
            provider: Имя провайдера.
            user_id: ID пользователя.
            db: Подключение к БД.

        Returns:
            str: Расшифрованный access token.

        Raises:
            ValueError: Если токен не найден.
        """
        token_data = await self._get_token_data(db, provider, user_id)
        if not token_data:
            raise ValueError(f"Токен не найден для {provider}")

        # Проверить истёк ли токен (с буфером 5 минут)
        expires_at = token_data["expires_at"]
        if datetime.utcnow() >= expires_at - timedelta(minutes=5):
            # Токен истёк или скоро истечёт, обновить
            logger.info("Token expired, refreshing", extra={
                        "provider": provider, "user_id": user_id})
            await self.refresh_token(provider, user_id, db)
            token_data = await self._get_token_data(db, provider, user_id)

        # Расшифровать и вернуть access token
        encrypted_token = token_data["access_token"]
        return self._decrypt_token(encrypted_token)

    async def disconnect(self, provider: str, user_id: int, db: asyncpg.Connection) -> None:
        """Отключает OAuth провайдера (удаляет токены).

        Args:
            provider: Имя провайдера.
            user_id: ID пользователя.
            db: Подключение к БД.
        """
        await self._delete_tokens(db, provider, user_id)
        logger.info("Disconnected OAuth provider", extra={
                    "provider": provider, "user_id": user_id})

    # Приватные методы

    def _encrypt_token(self, token: str) -> str:
        """Зашифровать токен"""
        return self.fernet.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Расшифровать токен"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()

    async def _store_state(self, db: asyncpg.Connection, state: str, provider: str, user_id: int) -> None:
        """Сохранить state в БД для CSRF защиты"""
        # State истекает через 10 минут
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        await db.execute(
            """
            INSERT INTO oauth_states (state, provider, user_id, expires_at)
            VALUES ($1, $2, $3, $4)
            """,
            state,
            provider,
            user_id,
            expires_at,
        )

    async def _verify_state(self, db: asyncpg.Connection, state: str, provider: str) -> Optional[int]:
        """
        Проверить state и вернуть user_id
        """
        # Найти state
        row = await db.fetchrow(
            """
            SELECT user_id FROM oauth_states
            WHERE state = $1 AND provider = $2 AND expires_at > NOW()
            """,
            state,
            provider,
        )

        if not row:
            return None

        user_id = row["user_id"]

        # Удалить state (one-time use)
        await db.execute("DELETE FROM oauth_states WHERE state = $1", state)

        return user_id

    async def _store_tokens(self, db: asyncpg.Connection, provider: str, user_id: int, token_data: Dict) -> None:
        """Сохранить токены в БД"""
        # Зашифровать токены
        access_token = self._encrypt_token(token_data["access_token"])
        refresh_token = None
        if "refresh_token" in token_data:
            refresh_token = self._encrypt_token(token_data["refresh_token"])

        # Вычислить expires_at
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Upsert токен
        await db.execute(
            """
            INSERT INTO oauth_tokens (provider, user_id, access_token, refresh_token, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, provider)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            """,
            provider,
            user_id,
            access_token,
            refresh_token,
            expires_at,
        )

    async def _get_token_data(self, db: asyncpg.Connection, provider: str, user_id: int) -> Optional[Dict]:
        """Получить token data из БД"""
        row = await db.fetchrow(
            """
            SELECT access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE provider = $1 AND user_id = $2
            """,
            provider,
            user_id,
        )

        if not row:
            return None

        return {
            "access_token": row["access_token"],
            "refresh_token": row["refresh_token"],
            "expires_at": row["expires_at"],
        }

    async def _get_refresh_token(self, db: asyncpg.Connection, provider: str, user_id: int) -> Optional[str]:
        """Получить refresh token из БД"""
        token_data = await self._get_token_data(db, provider, user_id)
        if not token_data or not token_data["refresh_token"]:
            return None

        return self._decrypt_token(token_data["refresh_token"])

    async def _delete_tokens(self, db: asyncpg.Connection, provider: str, user_id: int) -> None:
        """Удалить токены из БД"""
        await db.execute("DELETE FROM oauth_tokens WHERE provider = $1 AND user_id = $2", provider, user_id)
