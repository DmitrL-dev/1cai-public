"""
Доменные модели для модуля аутентификации.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class UserCredentials(BaseModel):
    """Модель учетных данных пользователя."""

    username: str
    password: str
    user_id: str
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    full_name: Optional[str] = None
    email: Optional[str] = None


class CurrentUser(BaseModel):
    """Модель текущего аутентифицированного пользователя."""

    user_id: str
    username: str
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    full_name: Optional[str] = None
    email: Optional[str] = None

    def has_role(self, *required_roles: str) -> bool:
        """Проверяет наличие хотя бы одной из указанных ролей.

        Args:
            required_roles: Список требуемых ролей.

        Returns:
            bool: True если есть роль, иначе False.
        """
        return any(role in self.roles for role in required_roles)

    def has_permission(self, *required_permissions: str) -> bool:
        """Проверяет наличие хотя бы одного из указанных прав.

        Args:
            required_permissions: Список требуемых прав.

        Returns:
            bool: True если есть право, иначе False.
        """
        return any(
            permission in self.permissions for permission in required_permissions
        )
