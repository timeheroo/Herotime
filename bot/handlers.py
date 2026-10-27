
"""Telegram bot command and menu handlers using Aiogram."""

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import OWNER_ID

logger = logging.getLogger(__name__)

router = Router()

MENU_BUTTONS = [
    "Channel Management",
    "Reaction Management",
    "Account Management",
    "Reports/Analytics",
    "Live Stream Management",
    "Admin Permissions",
]


def get_main_menu() -> ReplyKeyboardMarkup:
    """Build the main menu keyboard."""
    builder = ReplyKeyboardBuilder()

    for button_text in MENU_BUTTONS:
        builder.button(text=button_text)

    builder.adjust(2)

    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Respond to /start with the main menu."""
    if message.from_user is None:
        return

    await message.answer(
        "Welcome! Telegram Management Bot is running.\n\n"
        "Choose an option from the menu below.",
        reply_markup=get_main_menu(),
    )


@router.message()
async def menu_handler(message: Message) -> None:
    """Handle the main menu buttons."""
    if not message.text:
        return

    text = message.text.strip()

    if text == "Channel Management":
        response = "Channel Management\n\nChannel management features are being prepared."

    elif text == "Reaction Management":
        response = "Reaction Management\n\nView and configure permitted reaction settings."

    elif text == "Account Management":
        response = "Account Management\n\nAccount registration features are being prepared."

    elif text == "Reports/Analytics":
        response = "Reports/Analytics\n\nReports will show recorded data only."

    elif text == "Live Stream Management":
        response = "Live Stream Management\n\nMonitoring features are being prepared."

    elif text == "Admin Permissions":
        if message.from_user is None or message.from_user.id != OWNER_ID:
            await message.answer("Sorry, only the bot owner can access this menu.")
            return

        response = "Admin Permissions\n\nAdmin permission management is being prepared."

    else:
        return

    await message.answer(response)


async def register_handlers(dispatcher) -> None:
    """Register the bot router with the dispatcher."""
    dispatcher.include_router(router)
    logger.info("Bot handlers registered.")
