
"""Telegram bot menu keyboards."""

from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


# Six main menu buttons
MAIN_MENU_BUTTONS = [
    ["📢 Channel Management", "❤️ Reaction Management"],
    ["🔑 Account Management", "📊 Reports / Analytics"],
    ["📡 Live Stream Management", "👤 Admin Permissions"],
]


def get_main_menu() -> ReplyKeyboardMarkup:
    """Return the main reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=button) for button in row]
            for row in MAIN_MENU_BUTTONS
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )


def get_back_keyboard() -> ReplyKeyboardMarkup:
    """Return a keyboard with a back-to-menu button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Main Menu")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_confirmation_keyboard(
    confirm_callback: str,
    cancel_callback: str = "cancel",
) -> InlineKeyboardMarkup:
    """Create a reusable confirmation keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirm",
                    callback_data=confirm_callback,
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=cancel_callback,
                ),
            ]
        ]
    )
