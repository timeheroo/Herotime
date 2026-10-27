
"""Telegram bot command and menu handlers."""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.keyboards import get_main_menu, get_back_keyboard
from config import OWNER_ID

logger = logging.getLogger(__name__)


# -------------------------
# Start command
# -------------------------

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message) -> None:
    """Welcome the user and display the main menu."""
    user = message.from_user

    if user is None:
        return

    if user.id == OWNER_ID:
        greeting = "Welcome, Owner! 👋"
    else:
        greeting = "Welcome! 👋"

    await message.reply_text(
        f"{greeting}\n\n"
        "Telegram Management System\n\n"
        "Choose an option from the menu below:",
        reply_markup=get_main_menu(),
    )


# -------------------------
# Main menu handlers
# -------------------------

@Client.on_message(
    filters.private & filters.regex(r"^📢 Channel Management$")
)
async def channel_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "📢 Channel Management\n\n"
        "Channel listing and management features will be connected here.",
        reply_markup=get_back_keyboard(),
    )


@Client.on_message(
    filters.private & filters.regex(r"^❤️ Reaction Management$")
)
async def reaction_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "❤️ Reaction Management\n\n"
        "View and manage saved reaction preferences here. "
        "This menu does not generate artificial reactions.",
        reply_markup=get_back_keyboard(),
    )


@Client.on_message(
    filters.private & filters.regex(r"^🔑 Account Management$")
)
async def account_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "🔑 Account Management\n\n"
        "Account registration and status management will be connected here. "
        "Sensitive credentials must never be displayed in chat.",
        reply_markup=get_back_keyboard(),
    )


@Client.on_message(
    filters.private & filters.regex(r"^📊 Reports / Analytics$")
)
async def reports_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "📊 Reports / Analytics\n\n"
        "Choose a reporting period:",
        reply_markup=get_back_keyboard(),
    )


@Client.on_message(
    filters.private & filters.regex(r"^📡 Live Stream Management$")
)
async def live_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "📡 Live Stream Management\n\n"
        "Monitoring status and configured targets will be shown here. "
        "Configured targets are not actual viewer counts.",
        reply_markup=get_back_keyboard(),
    )


@Client.on_message(
    filters.private & filters.regex(r"^👤 Admin Permissions$")
)
async def admin_menu_handler(
    client: Client,
    message: Message,
) -> None:
    user = message.from_user

    if user is None or user.id != OWNER_ID:
        await message.reply_text(
            "⛔ Only the owner can access admin permission management."
        )
        return

    await message.reply_text(
        "👤 Admin Permissions\n\n"
        "Admin promotion and individual permission controls "
        "will be connected here.",
        reply_markup=get_back_keyboard(),
    )


# -------------------------
# Return to main menu
# -------------------------

@Client.on_message(
    filters.private & filters.regex(r"^⬅️ Main Menu$")
)
async def back_to_menu_handler(
    client: Client,
    message: Message,
) -> None:
    await message.reply_text(
        "Main menu:",
        reply_markup=get_main_menu(),
    )
