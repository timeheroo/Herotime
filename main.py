
"""Application entry point for the Telegram management bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database.connection import (
    close_database,
    create_tables,
    init_database,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()

    try:
        logger.info("Checking PostgreSQL connection...")
        await init_database()

        logger.info("Creating database tables...")
        await create_tables()

        # Handlers will be registered with Aiogram in the next step.
        logger.info("Starting Telegram bot...")
        await dispatcher.start_polling(bot)

    except Exception:
        logger.exception("Application startup or runtime failed.")
        raise

    finally:
        await bot.session.close()
        await close_database()
        logger.info("Application stopped.")


if __name__ == "__main__":
    asyncio.run(main())
