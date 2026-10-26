
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
)

from config import BOT_TOKEN
from database import (
    connect_database,
    init_database,
    close_database,
)

from handlers.start import get_start_handlers
from handlers.admin import get_admin_handlers
from handlers.channels import get_channel_handlers
from handlers.accounts import get_account_handlers
from handlers.live_stream import get_live_handlers
from handlers.reactions import get_reaction_handlers
from handlers.reports import get_report_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initialize the database when the bot starts."""
    await connect_database()
    await init_database()
    logger.info("Database initialized successfully.")


async def post_shutdown(application: Application) -> None:
    """Close database connections during shutdown."""
    await close_database()
    logger.info("Database connections closed.")


def main() -> None:
    """Build and run the Telegram bot."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register command and callback handlers from each module.
    handler_groups = [
        get_start_handlers,
        get_admin_handlers,
        get_channel_handlers,
        get_account_handlers,
        get_live_handlers,
        get_reaction_handlers,
        get_report_handlers,
    ]

    for get_handlers in handler_groups:
        for handler in get_handlers():
            application.add_handler(handler)

    logger.info("Starting Telegram management bot.")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
