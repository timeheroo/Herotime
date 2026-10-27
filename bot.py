
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, LOG_LEVEL
from database import connect_db, init_database, close_db

from handlers.start import get_start_handlers, get_menu_handlers
from handlers.admin import get_admin_handlers
from handlers.channels import get_channel_handlers
from handlers.accounts import get_account_handlers
from handlers.live_stream import get_live_handlers
from handlers.reactions import get_reaction_handlers
from handlers.reports import get_report_handlers


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Connect to PostgreSQL and prepare the database."""
    logger.info("Connecting to database...")

    await connect_db()
    await init_database()

    logger.info("Database initialization complete.")


async def post_shutdown(application: Application) -> None:
    """Close the database connection pool."""
    logger.info("Closing database connections...")
    await close_db()


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Log unexpected errors without exposing secrets to users."""
    logger.error(
        "Unhandled bot exception",
        exc_info=(
            type(context.error),
            context.error,
            context.error.__traceback__,
        ) if context.error else None,
    )


def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    handler_groups = [
        get_start_handlers(),
        get_admin_handlers(),
        get_channel_handlers(),
        get_account_handlers(),
        get_live_handlers(),
        get_reaction_handlers(),
        get_report_handlers(),
        get_menu_handlers(),
    ]

    for handlers in handler_groups:
        for handler in handlers:
            application.add_handler(handler)

    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
