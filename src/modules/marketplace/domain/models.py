from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PluginCategory(str, Enum):
    """Категории плагинов"""

    AI_AGENT = "ai_agent"
    CODE_TOOL = "code_tool"
    INTEGRATION = "integration"
    UI_THEME = "ui_theme"
    ANALYTICS = "analytics"
    SECURITY = "security"
    DEVOPS = "devops"
    OTHER = "other"


class PluginStatus(str, Enum):
    """Статус плагина в marketplace"""

    PENDING = "pending"  # На модерации
    APPROVED = "approved"  # Одобрен
    REJECTED = "rejected"  # Отклонен
    DEPRECATED = "deprecated"  # Устарел
    REMOVED = "removed"  # Удален


class PluginVisibility(str, Enum):
    """Видимость плагина"""

    PUBLIC = "public"  # Доступен всем
    PRIVATE = "private"  # Только автору
    UNLISTED = "unlisted"  # По прямой ссылке


class PluginSubmitRequest(BaseModel):
    """Запрос на публикацию плагина"""

    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    category: PluginCategory
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    author: str = Field(..., min_length=2, max_length=100)
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = Field(default="MIT")
    keywords: List[str] = Field(default_factory=list)
    visibility: PluginVisibility = PluginVisibility.PUBLIC

    # Compatibility
    min_version: str = Field(default="1.0.0")
    supported_platforms: List[str] = Field(
        default_factory=lambda: ["telegram", "mcp", "edt"])

    # Resources
    icon_url: Optional[str] = None
    screenshot_urls: List[str] = Field(default_factory=list)
    artifact_path: Optional[str] = Field(
        default=None, description="S3 object key with plugin bundle")

    # Documentation
    readme: Optional[str] = None
    changelog: Optional[str] = None


class PluginUpdateRequest(BaseModel):
    """Запрос на обновление плагина"""

    version: Optional[str] = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    changelog: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    keywords: Optional[List[str]] = None
    icon_url: Optional[str] = None
    screenshot_urls: Optional[List[str]] = None
    readme: Optional[str] = None
    artifact_path: Optional[str] = Field(
        None, description="S3 object key with plugin bundle")


class PluginSearchRequest(BaseModel):
    """Запрос поиска плагинов"""

    query: Optional[str] = None
    category: Optional[PluginCategory] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    sort_by: str = Field(default="rating")  # rating | downloads | updated | name
    order: str = Field(default="desc")  # asc | desc
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PluginResponse(BaseModel):
    """Ответ с информацией о плагине"""

    id: str
    plugin_id: str
    name: str
    description: str
    category: PluginCategory
    version: str
    author: str
    status: PluginStatus
    visibility: PluginVisibility

    # Stats
    downloads: int = 0
    rating: float = 0.0
    ratings_count: int = 0
    installs: int = 0

    # URLs
    homepage: Optional[str] = None
    repository: Optional[str] = None
    download_url: Optional[str] = None
    icon_url: Optional[str] = None
    screenshot_urls: List[str] = Field(default_factory=list)
    artifact_path: Optional[str] = None

    # Metadata
    license: str
    keywords: List[str] = Field(default_factory=list)
    min_version: str
    supported_platforms: List[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    # Features
    featured: bool = False
    verified: bool = False


class PluginReviewRequest(BaseModel):
    """Запрос на review плагина"""

    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)
    pros: Optional[str] = Field(None, max_length=200)
    cons: Optional[str] = Field(None, max_length=200)


class PluginReviewResponse(BaseModel):
    """Ответ с отзывом"""

    id: str
    plugin_id: str
    user_id: str
    user_name: str
    rating: int
    comment: Optional[str]
    pros: Optional[str]
    cons: Optional[str]
    helpful_count: int = 0
    created_at: datetime


class PluginSearchResponse(BaseModel):
    """Ответ на поиск плагинов"""

    plugins: List[PluginResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PluginStatsResponse(BaseModel):
    """Статистика плагина"""

    plugin_id: str
    downloads_total: int
    downloads_last_30_days: int
    installs_active: int
    rating_average: float
    rating_distribution: Dict[int, int]  # {5: 100, 4: 50, ...}
    reviews_count: int
    favorites_count: int

    # Trending
    downloads_trend: str  # "up" | "down" | "stable"
    rating_trend: str
