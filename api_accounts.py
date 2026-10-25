
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

logger = logging.getLogger(__name__)


async def add_api_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return

    await message.reply_text(
        "🔑 API Account Setup\n\n"
        "Command handler working hai ✅\n\n"
        "API ID aur API Hash ko is Telegram chat mein mat bhejein.\n"
        "Secure configuration ke liye Railway → Project → Variables "
        "ka use karein.\n\n"
        "Note: Ye test command abhi API credentials save ya account "
        "connect nahi karti."
    )


def register_api_handlers(application: Application) -> None:
    application.add_handler(
        CommandHandler("add_api", add_api_command)
    )
