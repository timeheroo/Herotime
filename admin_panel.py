
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_menu() -> InlineKeyboardMarkup:
    """Create the main admin panel with four approved sections."""

    keyboard = [
        [
            InlineKeyboardButton(
                "📂 CHANNELS LIST",
                callback_data="admin_channels",
            )
        ],
        [
            InlineKeyboardButton(
                "🔑 API ID / API HASH LIST",
                callback_data="admin_api_list",
            )
        ],
        [
            InlineKeyboardButton(
                "🛡️ ALL POWER LIST",
                callback_data="admin_all_power",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 REPORT",
                callback_data="admin_report",
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 BACK TO MAIN MENU",
                callback_data="home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def admin_back_menu() -> InlineKeyboardMarkup:
    """Create a reusable back-to-admin button."""

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 BACK TO ADMIN PANEL",
                callback_data="admin_panel",
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 BACK TO MAIN MENU",
                callback_data="home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)
