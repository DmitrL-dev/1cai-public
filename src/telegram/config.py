
"""
Telegram Bot Configuration
"""


from dataclasses import dataclass
from typing import Optional
from src.config import settings


@dataclass
class TelegramConfig:
    """Telegram bot configuration"""

    # Bot token from @BotFather
    bot_token: str

    # Admin user IDs (для контроля доступа)
    admin_ids: list[int]

    # Rate limiting
    max_requests_per_minute: int = 10
    max_requests_per_day: int = 100

    # Premium users (unlimited)
    premium_user_ids: set[int] = None

    # Features
    enable_code_generation: bool = True
    enable_dependency_analysis: bool = True
    enable_semantic_search: bool = True

    # Webhook settings (для production)
    webhook_url: Optional[str] = None
    webhook_path: str = "/telegram/webhook"
    webhook_port: int = 8443

    @classmethod
    def from_env(cls):
        """Load config from environment variables"""
        return cls(
            bot_token=settings.telegram_bot_token or "",
            admin_ids=[int(id) for id in settings.telegram_admin_ids.split(",") if id],
            max_requests_per_minute=settings.telegram_rate_limit_min,
            max_requests_per_day=settings.telegram_rate_limit_day,
            premium_user_ids=set([int(id) for id in settings.telegram_premium_ids.split(",") if id]),
            enable_code_generation=settings.telegram_enable_codegen,
            enable_dependency_analysis=settings.telegram_enable_deps,
            enable_semantic_search=settings.telegram_enable_search,
            webhook_url=settings.telegram_webhook_url,
            webhook_path=settings.telegram_webhook_path,
            webhook_port=settings.telegram_webhook_port,
        )


# Global config instance
config = TelegramConfig.from_env()
