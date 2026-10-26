
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import OWNER_ADMIN_ID


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle the /start command."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if user.id == OWNER_ADMIN_ID:
        await message.reply_text(
            "👑 Welcome, Owner Admin!\n\n"
            "Bot is running.\n"
            "Admin management aur channel controls "
            "setup hone ke baad available honge.\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/help - Help menu"
        )
    else:
        await message.reply_text(
            "Welcome!\n\n"
            "This bot is under setup. "
            "Please contact the Owner Admin for access."
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle the /help command."""
    message = update.effective_message

    if message is None:
        return

    await message.reply_text(
        "📋 Help Menu\n\n"
        "/start - Start the bot\n"
        "/help - Show available commands\n\n"
        "Additional admin commands will be added "
        "in the upcoming modules."
    )


def get_start_handlers():
    """Return the start-related command handlers."""
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
    ]
