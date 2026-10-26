
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, OWNER_ADMIN_ID
from database import (
    connect_database,
    init_database,
    close_database,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Reduce noisy logs and avoid printing sensitive request details.
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


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Respond to /start."""
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    if user.id == OWNER_ADMIN_ID:
        message = (
            "Welcome, Owner Admin!\n\n"
            "Bot is running.\n"
            "Admin commands will be added in the next files."
        )
    else:
        message = (
            "Welcome!\n\n"
            "This bot is under setup. "
            "Please contact the bot owner for access."
        )

    await update.effective_message.reply_text(message)


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show the currently available commands."""
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "More admin commands will be added in later files."
    )


def main() -> None:
    """Build and run the Telegram bot."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Starting Telegram management bot.")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
