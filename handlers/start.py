
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import OWNER_ADMIN_ID
from utils.permissions import get_admin


def owner_menu():
    keyboard = [
        [
            InlineKeyboardButton("👥 Manage Admins", callback_data="menu_admins"),
            InlineKeyboardButton("📢 Channels", callback_data="menu_channels"),
        ],
        [
            InlineKeyboardButton("📱 Accounts", callback_data="menu_accounts"),
            InlineKeyboardButton("🔴 Live Settings", callback_data="menu_live"),
        ],
        [
            InlineKeyboardButton("❤️ Reaction Settings", callback_data="menu_reactions"),
            InlineKeyboardButton("📊 Reports", callback_data="menu_reports"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="menu_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if user.id == OWNER_ADMIN_ID:
        await message.reply_text(
            "👑 Welcome, Owner Admin!\n\n"
            "Select an option from the menu below.",
            reply_markup=owner_menu(),
        )
        return

    admin = await get_admin(user.id)

    if admin:
        await message.reply_text(
            "Welcome, Sub-Admin!\n\n"
            "Use /help to view available commands."
        )
    else:
        await message.reply_text(
            "Welcome!\n\n"
            "You do not have admin access. Please contact the Owner Admin."
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    if message is None:
        return

    await message.reply_text(
        "📋 Help Menu\n\n"
        "/start - Open the menu\n"
        "/help - Show this help message\n\n"
        "Admin commands:\n"
        "/admins\n"
        "/addadmin USER_ID\n"
        "/removeadmin USER_ID\n"
        "/grant USER_ID PERMISSION\n"
        "/revoke USER_ID PERMISSION\n\n"
        "Channel commands:\n"
        "/addchannel @username\n"
        "/channels\n"
        "/activatechannel CHANNEL_ID\n"
        "/deactivatechannel CHANNEL_ID\n\n"
        "Account commands:\n"
        "/addaccount LABEL\n"
        "/accounts\n"
        "/deactivateaccount ID\n\n"
        "Live commands:\n"
        "/setlivetarget CHANNEL_ID QUANTITY\n"
        "/livetasks\n"
        "/startlive TASK_ID\n"
        "/stoplive TASK_ID\n\n"
        "Reaction commands:\n"
        "/setreaction CHANNEL_ID REACTION QUANTITY\n"
        "/reactiontasks\n"
        "/startreactions TASK_ID\n"
        "/stopreactions TASK_ID\n\n"
        "Reports:\n"
        "/report daily|weekly|monthly|24h|72h\n"
        "/recentactivity"
    )


async def menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    user = update.effective_user

    if query is None or user is None:
        return

    await query.answer()

    if user.id != OWNER_ADMIN_ID:
        await query.answer(
            "Only the Owner Admin can use this menu.",
            show_alert=True,
        )
        return

    messages = {
        "menu_admins": "👥 Admin Management\n\nUse /admins to list admins.",
        "menu_channels": "📢 Channel Management\n\nUse /channels to view channels.",
        "menu_accounts": "📱 Account Records\n\nUse /accounts to view records.",
        "menu_live": "🔴 Live Settings\n\nUse /livetasks to view live tasks.",
        "menu_reactions": "❤️ Reaction Settings\n\nUse /reactiontasks to view reaction tasks.",
        "menu_reports": "📊 Reports\n\nUse /report daily, weekly, monthly, 24h, or 72h.",
        "menu_help": "❓ Use /help to view the available commands.",
    }

    text = messages.get(query.data)

    if text:
        await query.message.reply_text(text)


def get_start_handlers():
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CallbackQueryHandler(menu_callback, pattern=r"^menu_"),
    ]
