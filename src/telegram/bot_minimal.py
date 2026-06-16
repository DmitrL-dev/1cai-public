
"""
MINIMAL Telegram Bot - Работает БЕЗ Docker, БЕЗ баз данных!
Только для быстрого старта
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiohttp import ClientTimeout

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Router
router = Router()

# Простое хранилище в памяти (НЕ для production!)
user_search_counts = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    user_name = message.from_user.first_name

    text = f"""👋 Привет, **{user_name}**!

Я AI-помощник для 1С разработчиков.

**Доступные команды:**
/help - Справка
/search - Поиск (demo)
/about - О боте

🚀 Попробуйте /search!
"""

    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка"""
    text = """📖 **Команды:**

/start - Начать
/help - Эта справка
/search <запрос> - Поиск (demo)
/stats - Статистика
/about - О проекте

**Demo режим:**
Полная версия требует подключения баз данных.
Сейчас работает в demo режиме для тестирования!

GitHub: [ссылка на ваш repo]
"""

    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


@router.message(Command("search"))
async def cmd_search(message: Message):
    """Поиск (demo)"""
    query = message.text.replace("/search", "").strip()

    if not query:
        await message.reply("❓ Укажите запрос\n\nПример: `/search расчет НДС`")
        return

    # Demo ответ
    await message.answer("🔍 Ищу...")

    # Симуляция поиска
    await asyncio.sleep(1)

    demo_results = f"""✨ **Demo результаты для:** "{query}"

**1. РассчитатьСуммуНДС()**
📁 РасчетыСервер.bsl
💬 Функция расчета суммы НДС
🎯 Релевантность: 95%

**2. ПолучитьСтавкуНДС()**
📁 НалоговыеРасчеты.bsl
💬 Получение ставки НДС
🎯 Релевантность: 87%

**3. РегистрацияНДС()**
📁 ДокументПродажи.bsl
💬 Регистрация НДС в учете
🎯 Релевантность: 76%

⚠️ **Demo режим!**
Полная версия использует Neo4j + Qdrant для реального семантического поиска.

Хотите полную версию? → /about
"""

    await message.reply(demo_results, parse_mode=ParseMode.MARKDOWN)

    # Tracking
    user_id = message.from_user.id
    user_search_counts[user_id] = user_search_counts.get(user_id, 0) + 1


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика"""
    user_id = message.from_user.id
    search_count = user_search_counts.get(user_id, 0)

    text = f"""📊 **Ваша статистика**

Запросов сделано: {search_count}

⚠️ Demo режим - данные в памяти
"""

    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


@router.message(Command("about"))
async def cmd_about(message: Message):
    """О проекте"""
    text = """🤖 **1C AI Assistant**

**Текущая версия:** Demo (minimal)

**Полная версия включает:**
• Семантический поиск (Neo4j + Qdrant)
• Генерация BSL кода (Ollama + Qwen3)
• Анализ зависимостей
• Интеграция с Cursor/VSCode

**Установка полной версии:**
1. Docker Compose (рекомендуется)
2. Или manual setup с базами данных

**Контакты:**
GitHub: [your_repo]
Telegram: @your_contact

**Open Source:** MIT License
"""

    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


@router.message(F.text)
async def handle_text(message: Message):
    """Обработка обычного текста"""

    # Игнорируем команды
    if message.text.startswith("/"):
        await message.reply("❓ Неизвестная команда. Используйте /help")
        return

    # Echo + подсказка
    await message.reply(
        f"💬 Получил: {message.text}\n\n"
        "Попробуйте команды:\n"
        "/search <запрос> - Поиск\n"
        "/help - Справка"
    )


async def main():
    """Main function"""

    # Получаем токен
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        print("\n❌ ОШИБКА: TELEGRAM_BOT_TOKEN не установлен!\n")
        print("Как получить токен:")
        print("1. Открой Telegram → @BotFather")
        print("2. Отправь /newbot")
        print("3. Следуй инструкциям")
        print("4. Скопируй токен")
        print("5. Создай .env файл:")
        print("   TELEGRAM_BOT_TOKEN=твой_токен\n")
        return

    logger.info("🤖 Starting MINIMAL Telegram Bot...")
    logger.info("⚠️  Demo mode - without databases")

    # Создаем бота
    timeout_seconds = float(os.getenv("TELEGRAM_HTTP_TIMEOUT", "10"))
    session = AiohttpSession(timeout=ClientTimeout(total=timeout_seconds))
    bot = Bot(token=bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info("Bot started", extra={"bot_username": bot_info.username})
        logger.info("Polling started")
        logger.info("Tip: Ctrl+C to stop")

        # Запускаем polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(
            "Error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(
            "Fatal error",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
