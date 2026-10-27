
"""Application entry point for the Telegram management bot."""

import asyncio
import logging

from pyrogram import Client, idle

from config import API_HASH, API_ID, BOT_TOKEN
from database.connection import close_database, create_tables, init_database


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize the database and start the Telegram bot."""

    bot = Client(
        name="management_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
        no_updates=False,
    )

    try:
        logger.info("Checking PostgreSQL connection...")
        await init_database()

        logger.info("Creating database tables...")
        await create_tables()

        logger.info("Starting Telegram bot...")
        await bot.start()

        logger.info("Telegram bot started successfully.")
        await idle()

    except Exception:
        logger.exception("Application startup or runtime failed.")
        raise

    finally:
        if getattr(bot, "is_connected", False):
            await bot.stop()

        await close_database()
        logger.info("Application stopped.")


if __name__ == "__main__":
    asyncio.run(main())
