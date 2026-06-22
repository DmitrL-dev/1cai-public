"""
Сервис приложения для модуля аутентификации.
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
from fastapi import HTTPException, status

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.auth.domain.models import CurrentUser, UserCredentials
from src.modules.auth.infrastructure.config import AuthSettings

logger = StructuredLogger(__name__).logger

DEFAULT_DEMO_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "user_id": "admin-1",
        "roles": ["admin", "moderator"],
        "permissions": ["marketplace:approve", "marketplace:verify"],
        "full_name": "Administrator",
        "email": "admin@example.com",
    },
    {
        "username": "developer",
        "password": "dev123",
        "user_id": "user-1",
        "roles": ["developer"],
        "permissions": ["marketplace:submit", "marketplace:review"],
        "full_name": "Sample Developer",
        "email": "developer@example.com",
    },
]


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def _uses_default_demo_credentials(raw_users: List[dict]) -> bool:
    default_credentials = {
        (entry["username"], entry["password"]) for entry in DEFAULT_DEMO_USERS
    }
    return any(
        isinstance(entry, dict)
        and (str(entry.get("username")), str(entry.get("password")))
        in default_credentials
        for entry in raw_users
    )


class AuthService:
    """Сервис для аутентификации пользователей и выдачи JWT токенов."""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self._users: Dict[str, UserCredentials] = self._load_users()
        self._service_tokens: Dict[str, CurrentUser] = self._load_service_tokens()

        if self.settings.jwt_secret == "CHANGE_ME":
            if _is_production():
                raise RuntimeError(
                    "JWT_SECRET must be set to a strong non-default value in production."
                )
            logger.warning(
                "JWT_SECRET uses default value. Set a secure secret for production!"
            )

    def _load_users(self) -> Dict[str, UserCredentials]:
        raw_users: List[dict]
        if self.settings.demo_users:
            try:
                raw_users = json.loads(self.settings.demo_users)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse AUTH_DEMO_USERS JSON: %s", exc)
                if _is_production():
                    raise RuntimeError(
                        "AUTH_DEMO_USERS must contain valid JSON in production."
                    ) from exc
                raw_users = DEFAULT_DEMO_USERS
        else:
            if os.getenv("AUTH_DEMO_USERS") is None:
                if _is_production():
                    raise RuntimeError(
                        "AUTH_DEMO_USERS is required in production; "
                        "default demo users are disabled."
                    )
                logger.info(
                    "Using default demo users. Configure AUTH_DEMO_USERS for production."
                )
            raw_users = DEFAULT_DEMO_USERS

        if _is_production() and _uses_default_demo_credentials(raw_users):
            raise RuntimeError(
                "AUTH_DEMO_USERS contains default demo credentials, which are "
                "disabled in production."
            )

        users: Dict[str, UserCredentials] = {}
        for entry in raw_users:
            try:
                user = UserCredentials(**entry)
            except Exception as exc:  # noqa: BLE001
                logger.error("Invalid user entry skipped: %s", exc)
                continue
            users[user.username] = user
        return users

    def _load_service_tokens(self) -> Dict[str, CurrentUser]:
        if not self.settings.service_tokens:
            return {}

        try:
            data = json.loads(self.settings.service_tokens)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse SERVICE_API_TOKENS JSON: %s", exc)
            return {}

        token_map: Dict[str, CurrentUser] = {}

        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = []
            for name, values in data.items():
                if isinstance(values, dict):
                    values.setdefault("name", name)
                    entries.append(values)
        else:
            logger.error("SERVICE_API_TOKENS must be dict or list")
            return {}

        for entry in entries:
            try:
                token_value = entry.get("token")
                name = entry.get("name") or entry.get("service")
                if not token_value or not name:
                    raise ValueError("Missing name or token")
                roles = entry.get("roles") or ["service"]
                permissions = entry.get("permissions") or []
                principal = CurrentUser(
                    user_id=f"service:{name}",
                    username=name,
                    roles=roles,
                    permissions=permissions,
                    full_name=entry.get("description"),
                    email=None,
                )
                token_map[token_value] = principal
            except Exception as exc:  # noqa: BLE001
                logger.error("Invalid service token configuration skipped: %s", exc)
        if token_map and self.settings.service_tokens:
            logger.info("Loaded %d service API tokens", len(token_map))
        return token_map

    def authenticate_user(
        self, username: str, password: str
    ) -> Optional[UserCredentials]:
        """Аутентифицирует пользователя по имени и паролю.

        Args:
            username: Имя пользователя.
            password: Пароль (plain text).

        Returns:
            Optional[UserCredentials]: Объект пользователя если успех, иначе None.
        """
        user = self._users.get(username)
        if not user:
            return None
        if not secrets.compare_digest(password, user.password):
            return None
        return user

    def create_access_token(
        self, user: UserCredentials, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Создает JWT токен доступа (access token).

        Args:
            user: Объект пользователя.
            expires_delta: Время жизни токена (опционально).

        Returns:
            str: Закодированный JWT токен.
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.settings.access_token_expire_minutes)

        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.user_id,  # Subject (user ID)
            "username": user.username,
            "roles": user.roles,
            "permissions": user.permissions,
            "full_name": user.full_name,
            "email": user.email,
            "iat": int(now.timestamp()),  # Issued at (Unix timestamp)
            # Expiration (Unix timestamp)
            "exp": int((now + expires_delta).timestamp()),
            "type": "access",  # Token type for clarity
        }

        # Best practice: Use secure secret and algorithm
        token = jwt.encode(
            payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm
        )
        return token

    def create_refresh_token(self, user: UserCredentials) -> str:
        """Создает токен обновления (refresh token).

        Args:
            user: Объект пользователя.

        Returns:
            str: Закодированный JWT токен.
        """
        expires_delta = timedelta(days=7)  # Refresh tokens last 7 days
        now = datetime.now(timezone.utc)

        payload = {
            "sub": user.user_id,
            "username": user.username,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
            "type": "refresh",  # Different type for refresh tokens
        }

        # Use same secret but different type
        token = jwt.encode(
            payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm
        )
        return token

    def decode_token(self, token: str, token_type: str = "access") -> CurrentUser:
        """Декодирует и валидирует JWT токен.

        Args:
            token: JWT токен.
            token_type: Ожидаемый тип токена (access/refresh).

        Returns:
            CurrentUser: Объект пользователя из токена.

        Raises:
            HTTPException: Если токен невалиден, истек или имеет неверный тип.
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            logger.warning(
                "JWT expired",
                extra={"error_type": "ExpiredSignatureError", "token_type": token_type},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired. Please refresh your token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except jwt.InvalidTokenError as exc:
            logger.warning(
                "JWT invalid",
                extra={"error_type": "InvalidTokenError", "token_type": token_type},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Please authenticate again.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except jwt.PyJWTError as exc:
            logger.warning(
                "JWT decode error",
                extra={"error_type": type(exc).__name__, "token_type": token_type},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        # Validate token type
        if payload.get("type") != token_type:
            logger.warning(
                "Invalid token type",
                extra={"expected_type": token_type, "actual_type": payload.get("type")},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate required fields
        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return CurrentUser(
            user_id=user_id,
            username=username,
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            full_name=payload.get("full_name"),
            email=payload.get("email"),
        )

    def authenticate_service_token(self, token: str) -> Optional[CurrentUser]:
        """Аутентифицирует сервисный токен.

        Args:
            token: Сервисный токен (API Key).

        Returns:
            Optional[CurrentUser]: Объект сервисного пользователя если токен валиден.
        """
        if not token:
            return None
        principal = self._service_tokens.get(token)
        if principal:
            return principal
        return None
