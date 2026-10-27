
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import OWNER_ADMIN_ID
from utils.permissions import has_permission, get_admin


MENUS = {
    "admins": {
        "title": "👥 Admin Management",
        "permission": "manage_admins",
        "commands": [
            ("📋 List admins", "/admins"),
            ("➕ Add admin", "Usage: /addadmin USER_ID"),
            ("➖ Remove admin", "Usage: /removeadmin USER_ID"),
            ("🔐 Grant permission", "Usage: /grant USER_ID PERMISSION"),
            ("🔒 Revoke permission", "Usage: /revoke USER_ID PERMISSION"),
        ],
    },
    "channels": {
        "title": "📢 Channel Management",
        "permission": "manage_channels",
        "commands": [
            ("📋 List channels", "/channels"),
            ("➕ Add channel", "Usage: /addchannel @username"),
            ("🟢 Activate channel", "Usage: /activatechannel CHANNEL_ID"),
            ("🔴 Deactivate channel", "Usage: /deactivatechannel CHANNEL_ID"),
        ],
    },
    "accounts": {
        "title": "📱 Account Records",
        "permission": "manage_accounts",
        "commands": [
            ("📋 List accounts", "/accounts"),
            ("➕ Add account record", "Usage: /addaccount ACCOUNT_LABEL"),
            ("🔴 Deactivate account", "Usage: /deactivateaccount ACCOUNT_ID"),
        ],
    },
    "live": {
        "title": "🔴 Live Settings",
        "permission": "manage_live",
        "commands": [
            ("📋 View live tasks", "/livetasks"),
            ("🎯 Set target", "Usage: /setlivetarget CHANNEL_ID QUANTITY"),
            ("▶️ Start task", "Usage: /startlive TASK_ID"),
            ("⏹ Stop task", "Usage: /stoplive TASK_ID"),
        ],
    },
    "reactions": {
        "title": "❤️ Reaction Settings",
        "permission": "manage_reactions",
        "commands": [
            ("📋 View reaction tasks", "/reactiontasks"),
            ("⚙️ Set reaction", "Usage: /setreaction CHANNEL_ID REACTION QUANTITY"),
            ("▶️ Start task", "Usage: /startreactions TASK_ID"),
            ("⏹ Stop task", "Usage: /stopreactions TASK_ID"),
        ],
    },
    "reports": {
        "title": "📊 Reports",
        "permission": "view_reports",
        "commands": [
            ("📅 Daily", "/report daily"),
            ("📆 Weekly", "/report weekly"),
            ("🗓 Monthly", "/report monthly"),
            ("🕐 Last 24 hours", "/report 24h"),
            ("🕒 Last 72 hours", "/report 72h"),
            ("🧾 Recent activity", "/recentactivity"),
        ],
    },
}


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    rows = []

    if user_id == OWNER_ADMIN_ID:
        permissions = set(MENUS.keys())
    else:
        permissions = set()

    # Permission checks are performed asynchronously in start_command.
    # This helper builds the keyboard from the supplied allowed sections.
    for key, label in [
        ("admins", "👥 Manage Admins"),
        ("channels", "📢 Channels"),
        ("accounts", "📱 Accounts"),
        ("live", "🔴 Live Settings"),
        ("reactions", "❤️ Reaction Settings"),
        ("reports", "📊 Reports"),
    ]:
        if key in permissions:
            rows.append([
                InlineKeyboardButton(label, callback_data=f"section_{key}")
            ])

    rows.append([
        InlineKeyboardButton("❓ Help", callback_data="section_help")
    ])
    return InlineKeyboardMarkup(rows)


async def get_allowed_sections(user_id: int) -> list[str]:
    if user_id == OWNER_ADMIN_ID:
        return list(MENUS.keys())

    allowed = []
    for key, menu in MENUS.items():
        if await has_permission(user_id, menu["permission"]):
            allowed.append(key)

    return allowed


def build_main_menu(sections: list[str]) -> InlineKeyboardMarkup:
    labels = {
        "admins": "👥 Manage Admins",
        "channels": "📢 Channels",
        "accounts": "📱 Accounts",
        "live": "🔴 Live Settings",
        "reactions": "❤️ Reaction Settings",
        "reports": "📊 Reports",
    }

    rows = [
        [InlineKeyboardButton(labels[key], callback_data=f"section_{key}")]
        for key in sections
        if key in labels
    ]
    rows.append([
        InlineKeyboardButton("❓ Help", callback_data="section_help")
    ])
    return InlineKeyboardMarkup(rows)


def build_section_menu(section: str) -> InlineKeyboardMarkup:
    menu = MENUS[section]
    rows = []

    for label, command in menu["commands"]:
        rows.append([
            InlineKeyboardButton(label, callback_data=f"info_{section}_{len(rows)}")
        ])

    rows.append([
        InlineKeyboardButton("⬅️ Main Menu", callback_data="section_home")
    ])
    return InlineKeyboardMarkup(rows)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    sections = await get_allowed_sections(user.id)

    if user.id != OWNER_ADMIN_ID and not sections:
        admin = await get_admin(user.id)
        if admin is None:
            await message.reply_text(
                "Welcome!\n\nAccess nahi mila hai. Owner Admin se contact karein."
            )
        else:
            await message.reply_text(
                "Aapke account par abhi koi management permission nahi hai. "
                "Owner Admin se permission lein."
            )
        return

    role = "Owner Admin" if user.id == OWNER_ADMIN_ID else "Admin"
    await message.reply_text(
        f"👑 Welcome, {role}!\n\nMenu se ek section select karein:",
        reply_markup=build_main_menu(sections),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    sections = await get_allowed_sections(user.id)
    if user.id != OWNER_ADMIN_ID and not sections:
        await message.reply_text(
            "Help aur management commands ke liye Owner Admin se access lein."
        )
        return

    lines = [
        "📋 Help Menu",
        "",
        "/start - Open menu",
        "/help - Show help",
    ]

    for section in sections:
        if section in MENUS:
            lines.append("")
            lines.append(MENUS[section]["title"])
            for _, command in MENUS[section]["commands"]:
                lines.append(command)

    await message.reply_text("\n".join(lines))


async def menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    user = update.effective_user

    if query is None or user is None:
        return

    data = query.data or ""
    sections = await get_allowed_sections(user.id)

    if data == "section_help":
        await query.answer()
        await query.message.reply_text(
            "❓ Help\n\n/start - Main menu\n/help - Available commands"
        )
        return

    if data == "section_home":
        await query.answer()
        await query.message.reply_text(
            "🏠 Main Menu",
            reply_markup=build_main_menu(sections),
        )
        return

    if data.startswith("section_"):
        section = data.removeprefix("section_")

        if section not in MENUS or section not in sections:
            await query.answer(
                "Aapke paas is section ki permission nahi hai.",
                show_alert=True,
            )
            return

        await query.answer()
        await query.message.reply_text(
            f"{MENUS[section]['title']}\n\n"
            "Neeche option select karein. Command ko use karne ke liye "
            "button ke saath dikhayi gayi command ko chat mein bhejein.",
            reply_markup=build_section_menu(section),
        )
        return

    if data.startswith("info_"):
        parts = data.split("_")
        if len(parts) < 3:
            await query.answer("Invalid option.", show_alert=True)
            return

        section = parts[1]
        if section not in MENUS or section not in sections:
            await query.answer(
                "Aapke paas is section ki permission nahi hai.",
                show_alert=True,
            )
            return

        try:
            index = int(parts[2])
            label, command = MENUS[section]["commands"][index]
        except (ValueError, IndexError):
            await query.answer("Option nahi mila.", show_alert=True)
            return

        await query.answer()
        await query.message.reply_text(
            f"{label}\n\n{command}\n\n"
            "Note: Yeh button command ki details dikhata hai; "
            "command ko chat mein alag se bhejna hoga."
        )
        return

    await query.answer("Unknown menu option.", show_alert=True)


def get_start_handlers():
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CallbackQueryHandler(
            menu_callback,
            pattern=r"^(section_|info_)",
        ),
    ]
