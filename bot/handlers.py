"""Telegram bot handlers and interactive management menus."""

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from config import OWNER_ID

logger = logging.getLogger(__name__)
router = Router()

MAIN_MENU_BUTTONS = [
    "Channel Management",
    "Reaction Management",
    "Account Management",
    "Reports/Analytics",
    "Live Stream Management",
    "Admin Permissions",
]

REACTION_MENU_BUTTONS = [
    "Service Reaction",
    "Channel Reaction",
    "⬅️ Back to Main Menu",
]


def make_keyboard(
    buttons: list[str],
    columns: int = 2,
) -> ReplyKeyboardMarkup:
    """Create a reply keyboard with the requested number of columns."""
    if columns < 1:
        raise ValueError("columns must be at least 1")

    rows = [
        [
            KeyboardButton(text=buttons[index])
            for index in range(start, min(start + columns, len(buttons)))
        ]
        for start in range(0, len(buttons), columns)
    ]

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_main_menu() -> ReplyKeyboardMarkup:
    return make_keyboard(MAIN_MENU_BUTTONS, columns=2)


def get_reaction_menu() -> ReplyKeyboardMarkup:
    return make_keyboard(REACTION_MENU_BUTTONS, columns=1)


def get_service_reaction_menu() -> ReplyKeyboardMarkup:
    return make_keyboard(
        [
            "📋 List Reaction Accounts",
            "⬅️ Back to Reaction Menu",
            "🏠 Back to Main Menu",
        ],
        columns=1,
    )


def get_channel_reaction_menu() -> ReplyKeyboardMarkup:
    return make_keyboard(
        [
            "📋 List Channels",
            "➕ Set Reaction Quantity",
            "▶️ Start Reaction Service",
            "⏹ Stop Reaction Service",
            "⬅️ Back to Reaction Menu",
            "🏠 Back to Main Menu",
        ],
        columns=1,
    )


async def show_main_menu(message: Message) -> None:
    await message.answer(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=get_main_menu(),
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    if message.from_user is None:
        return

    await message.answer(
        "Welcome! Telegram Management Bot is running.\n\n"
        "Choose an option from the menu below.",
        reply_markup=get_main_menu(),
    )


@router.message(F.text == "Reaction Management")
async def reaction_management_handler(message: Message) -> None:
    await message.answer(
        "❤️ <b>Reaction Management</b>\n\n"
        "Please select an option:",
        reply_markup=get_reaction_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "Service Reaction")
async def service_reaction_handler(message: Message) -> None:
    await message.answer(
        "👥 <b>Service Reaction</b>\n\n"
        "Registered reaction accounts will appear here after database "
        "integration. Account data is not connected yet.",
        reply_markup=get_service_reaction_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "Channel Reaction")
async def channel_reaction_handler(message: Message) -> None:
    await message.answer(
        "📊 <b>Channel Reaction</b>\n\n"
        "Channel-wise reaction quantities and service controls will appear "
        "here after database integration. Channel data is not connected yet.",
        reply_markup=get_channel_reaction_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "📋 List Reaction Accounts")
async def list_reaction_accounts_handler(message: Message) -> None:
    await message.answer(
        "📋 <b>Reaction Accounts</b>\n\n"
        "No accounts have been loaded. Database integration is still needed.",
        parse_mode="HTML",
    )


@router.message(F.text == "📋 List Channels")
async def list_reaction_channels_handler(message: Message) -> None:
    await message.answer(
        "📋 <b>Channel List</b>\n\n"
        "No channels have been loaded. Database integration is still needed.",
        parse_mode="HTML",
    )


@router.message(F.text == "➕ Set Reaction Quantity")
async def set_reaction_quantity_handler(message: Message) -> None:
    await message.answer(
        "➕ <b>Set Reaction Quantity</b>\n\n"
        "This feature needs channel selection and database integration "
        "before a quantity can be saved.",
        parse_mode="HTML",
    )


@router.message(F.text == "▶️ Start Reaction Service")
async def start_reaction_service_handler(message: Message) -> None:
    await message.answer(
        "▶️ <b>Start Reaction Service</b>\n\n"
        "No service was started. Channel configuration, authorization, "
        "and service implementation must be completed first.",
        parse_mode="HTML",
    )


@router.message(F.text == "⏹ Stop Reaction Service")
async def stop_reaction_service_handler(message: Message) -> None:
    await message.answer(
        "⏹ <b>Stop Reaction Service</b>\n\n"
        "No active service status is connected yet.",
        parse_mode="HTML",
    )


@router.message(F.text == "⬅️ Back to Reaction Menu")
async def back_to_reaction_menu_handler(message: Message) -> None:
    await message.answer(
        "❤️ Reaction Management\n\nPlease select an option:",
        reply_markup=get_reaction_menu(),
    )


@router.message(
    F.text.in_({"🏠 Back to Main Menu", "⬅️ Back to Main Menu"})
)
async def back_to_main_menu_handler(message: Message) -> None:
    await show_main_menu(message)


@router.message(F.text == "Channel Management")
async def channel_management_handler(message: Message) -> None:
    await message.answer(
        "📢 <b>Channel Management</b>\n\n"
        "Add, list, and remove features require database/API integration.",
        parse_mode="HTML",
    )


@router.message(F.text == "Account Management")
async def account_management_handler(message: Message) -> None:
    await message.answer(
        "👤 <b>Account Management</b>\n\n"
        "Account registration and secure credential management are not "
        "implemented yet.",
        parse_mode="HTML",
    )


@router.message(F.text == "Reports/Analytics")
async def reports_handler(message: Message) -> None:
    await message.answer(
        "📈 <b>Reports/Analytics</b>\n\n"
        "Reports will be available after database integration.",
        parse_mode="HTML",
    )


@router.message(F.text == "Live Stream Management")
async def live_stream_handler(message: Message) -> None:
    await message.answer(
        "🔴 <b>Live Stream Management</b>\n\n"
        "Monitoring controls are not implemented yet.",
        parse_mode="HTML",
    )


@router.message(F.text == "Admin Permissions")
async def admin_permissions_handler(message: Message) -> None:
    if message.from_user is None or message.from_user.id != OWNER_ID:
        await message.answer(
            "Sorry, only the bot owner can access this menu."
        )
        return

    await message.answer(
        "🛡️ <b>Admin Permissions</b>\n\n"
        "Admin management and per-feature permissions are not implemented yet.",
        parse_mode="HTML",
    )


async def register_handlers(dispatcher) -> None:
    """Register this router with the Aiogram dispatcher."""
    dispatcher.include_router(router)
    logger.info("Bot handlers registered.")
