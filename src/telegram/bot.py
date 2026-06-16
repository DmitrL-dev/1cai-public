
"""
Telegram Bot - Main entry point
Интеграция с 1C AI Assistant
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.telegram.config import config
from src.telegram.handlers import router
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


async def main():
    """Main bot function"""

    # Проверка конфигурации
    if not config.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        logger.info("Get token from @BotFather: https://t.me/BotFather")
        return

    logger.info("🤖 Starting 1C AI Assistant Telegram Bot...")

    # Initialize bot
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # Initialize dispatcher
    dp = Dispatcher()
    dp.include_router(router)

    # Startup message
    try:
        bot_info = await bot.get_me()
        logger.info("Bot started", extra={"bot_username": bot_info.username})
        logger.info(
            "Rate limits configured",
            extra={
                "max_per_minute": config.max_requests_per_minute,
                "max_per_day": config.max_requests_per_day,
            },
        )

        if config.admin_ids:
            logger.info("Admin IDs configured", extra={"admin_ids": config.admin_ids})

        if config.premium_user_ids:
            logger.info(
                "Premium users configured",
                extra={"premium_users_count": len(config.premium_user_ids)},
            )

        # Start polling
        logger.info("Starting polling")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except Exception as e:
        logger.error(
            "Bot error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(
            "Fatal error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        sys.exit(1)
