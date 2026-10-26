
# admin_power.py
# Admin Command Directory + Under Admin Permissions
# Existing PostgreSQL data ko delete/reset nahi karta.

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import config
import database

logger = logging.getLogger(__name__)

# Aapki di hui command list.
COMMAND_GROUPS = {
    "GENERAL ADMIN": [
        ("admin", "Admin panel open kare"),
        ("addnewadmin", "Naya under-admin add kare"),
        ("Removeadmin", "Under-admin remove kare"),
        ("Poweradmin", "Admin permissions manage kare"),
        ("adminalllist", "Admin commands ki list dikhaye"),
        ("admin_help", "Admin help dikhaye"),
        ("admin_stats", "Bot statistics dikhaye"),
        ("bot_status", "Bot status dikhaye"),
    ],
    "CHANNEL / GROUP MANAGEMENT": [
        ("add_group", "Channel/group add kare"),
        ("Remove_grounp", "Channel/group remove kare"),
        ("list_groups", "Channels/groups list kare"),
        ("Search_group", "Channel/group search kare"),
        ("group_info", "Channel/group details dikhaye"),
        ("pause_group", "Service pause kare"),
        ("resume_group", "Service resume kare"),
    ],
    "SERVICE & QUANTITY": [
        ("set_quantity", "Quantity set kare"),
        ("Increase_quantity", "Quantity badhaye"),
        ("decrease_quantity", "Quantity kam kare"),
        ("start_service", "Service start kare"),
        ("stop_service", "Service stop kare"),
        ("live_status", "Live status dikhaye"),
        ("all_services", "Services ki list dikhaye"),
    ],
    "API & ACCOUNT MANAGEMENT": [
        ("api_accounts", "Saved API accounts dikhaye"),
        ("add_api", "API account add kare"),
        ("api_info", "API details dikhaye"),
        ("rename_account", "Account ka naam badle"),
        ("update_api", "API details update kare"),
        ("remove_api", "API account remove kare"),
        ("rename_profile", "Profile ka naam badle"),
        ("Account_status", "Account status dikhaye"),
        ("Disconnect_account", "Account disconnect kare"),
    ],
    "REPORTS": [
        ("daily_report", "Daily report"),
        ("Weekly_report", "Weekly report"),
        ("Monthly_report", "Monthly report"),
        ("Last24h", "Last 24 hours report"),
        ("Last72", "Last 72 hours report"),
        ("Channel_report", "Channel/group report"),
        ("quantity_report", "Quantity report"),
    ],
}

# Telegram command names case-sensitive nahi hote; canonical names lowercase rakhein.
def canonical(command: str) -> str:
    return command.strip().lstrip("/").lower()


ALL_COMMANDS = {
    canonical(name): (name, description, category)
    for category, commands in COMMAND_GROUPS.items()
    for name, description in commands
}


async def init_admin_power_schema():
    """Sirf nayi permissions table create karta hai; existing tables ko touch nahi karta."""
    async with database.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_command_permissions (
                admin_telegram_id BIGINT NOT NULL,
                command_name TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                updated_by BIGINT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (admin_telegram_id, command_name)
            )
        """)


def _category_keyboard():
    rows = []
    for category in COMMAND_GROUPS:
        rows.append([
            InlineKeyboardButton(
                category,
                callback_data=f"power:cat:{list(COMMAND_GROUPS).index(category)}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            "👥 UNDER ADMIN",
            callback_data="power:admins",
        )
    ])
    rows.append([
        InlineKeyboardButton("🔙 Admin Menu", callback_data="admin_panel")
    ])
    return InlineKeyboardMarkup(rows)


async def _show_directory(query):
    lines = ["🛡️ ADMIN CONTROL PANEL — COMMAND DIRECTORY", ""]
    for category, commands in COMMAND_GROUPS.items():
        lines.append(f"📌 {category}")
        for name, description in commands:
            lines.append(f"/{name} — {description}")
        lines.append("")

    await query.edit_message_text(
        "\n".join(lines)[:4000],
        reply_markup=_category_keyboard(),
    )


async def _show_admins(query):
    owner_ids = config.ADMIN_IDS

    async with database.connection() as conn:
        # Existing users table ke known columns use kiye ja rahe hain.
        rows = await conn.fetch("""
            SELECT telegram_id, display_name, username, role, status
            FROM users
            WHERE LOWER(COALESCE(role, '')) IN ('admin', 'under_admin')
              AND status = 'approved'
            ORDER BY display_name NULLS LAST
            LIMIT 100
        """)

    rows = [r for r in rows if int(r["telegram_id"]) not in owner_ids]

    keyboard = []
    for row in rows:
        label = row["display_name"] or row["username"] or str(row["telegram_id"])
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {label} · {row['telegram_id']}",
                callback_data=f"power:user:{row['telegram_id']}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="power:directory")
    ])

    message = "👥 UNDER ADMIN LIST\n\n"
    if not rows:
        message += "Abhi database mein koi approved under-admin nahi mila.\n"
        message += "Pehle admin ko add/approve karna hoga."
    else:
        message += "Jis admin ki powers manage karni hain, use select karein."

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_user_permissions(query, target_id: int, category_index: int = 0):
    categories = list(COMMAND_GROUPS)
    category_index = max(0, min(category_index, len(categories) - 1))
    category = categories[category_index]

    async with database.connection() as conn:
        rows = await conn.fetch("""
            SELECT command_name, enabled
            FROM admin_command_permissions
            WHERE admin_telegram_id = $1
        """, target_id)

    saved = {canonical(r["command_name"]): r["enabled"] for r in rows}

    keyboard = []
    for name, description in COMMAND_GROUPS[category]:
        key = canonical(name)
        enabled = saved.get(key, False)
        state = "🟢 ON" if enabled else "🔴 OFF"
        keyboard.append([
            InlineKeyboardButton(
                f"{state}  /{name}",
                callback_data=f"power:toggle:{target_id}:{key}:{category_index}",
            )
        ])

    nav = []
    if category_index > 0:
        nav.append(InlineKeyboardButton(
            "⬅️ Previous",
            callback_data=f"power:usercat:{target_id}:{category_index - 1}",
        ))
    if category_index < len(categories) - 1:
        nav.append(InlineKeyboardButton(
            "Next ➡️",
            callback_data=f"power:usercat:{target_id}:{category_index + 1}",
        ))
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton("👥 Under Admin List", callback_data="power:admins")
    ])
    keyboard.append([
        InlineKeyboardButton("📚 Command Directory", callback_data="power:directory")
    ])

    await query.edit_message_text(
        f"🛡️ ADMIN POWERS\n"
        f"Admin Telegram ID: {target_id}\n"
        f"Category: {category}\n\n"
        "Har button par click karke command ki permission ON/OFF karein.\n"
        "Default permission: OFF.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_power_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    actor_id = query.from_user.id

    # Permission manage karne ka adhikar sirf configured owner ko.
    if not config.is_admin(actor_id):
        await query.answer("⛔ Sirf owner permissions manage kar sakta hai.", show_alert=True)
        return

    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "directory":
            await _show_directory(query)
            return

        if action == "admins":
            await _show_admins(query)
            return

        if action == "cat":
            index = int(parts[2])
            category = list(COMMAND_GROUPS)[index]
            lines = [f"📌 {category}", ""]
            for name, description in COMMAND_GROUPS[category]:
                lines.append(f"/{name} — {description}")
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 UNDER ADMIN", callback_data="power:admins")],
                    [InlineKeyboardButton("📚 Full Directory", callback_data="power:directory")],
                ]),
            )
            return

        if action == "user":
            await _show_user_permissions(query, int(parts[2]))
            return

        if action == "usercat":
            await _show_user_permissions(query, int(parts[2]), int(parts[3]))
            return

        if action == "toggle":
            target_id = int(parts[2])
            command_name = canonical(parts[3])
            category_index = int(parts[4])

            if command_name not in ALL_COMMANDS:
                await query.answer("Unknown command.", show_alert=True)
                return

            async with database.connection() as conn:
                target = await conn.fetchrow(
                    "SELECT telegram_id, role FROM users WHERE telegram_id = $1",
                    target_id,
                )
                if not target or target_id in config.ADMIN_IDS:
                    await query.answer("Owner ya unknown user ki permission change nahi ho sakti.", show_alert=True)
                    return

                # Current state check and toggle.
                current = await conn.fetchval("""
                    SELECT enabled FROM admin_command_permissions
                    WHERE admin_telegram_id = $1 AND LOWER(command_name) = $2
                """, target_id, command_name)

                new_state = not bool(current)
                await conn.execute("""
                    INSERT INTO admin_command_permissions
                        (admin_telegram_id, command_name, enabled, updated_by, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (admin_telegram_id, command_name)
                    DO UPDATE SET enabled = EXCLUDED.enabled,
                                  updated_by = EXCLUDED.updated_by,
                                  updated_at = NOW()
                """, target_id, command_name, new_state, actor_id)

            await _show_user_permissions(query, target_id, category_index)
            return

    except Exception:
        logger.exception("Admin power panel error")
        await query.edit_message_text(
            "❌ Panel error. Railway logs check karein.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Directory", callback_data="power:directory")
            ]]),
        )


async def has_command_permission(telegram_id: int, command: str) -> bool:
    """Owner always allowed; under-admin requires explicit ON."""
    if config.is_admin(telegram_id):
        return True

    key = canonical(command)
    if key not in ALL_COMMANDS:
        return False

    async with database.connection() as conn:
        row = await conn.fetchrow("""
            SELECT enabled
            FROM admin_command_permissions
            WHERE admin_telegram_id = $1
              AND LOWER(command_name) = $2
            LIMIT 1
        """, telegram_id, key)

    return bool(row and row["enabled"])


async def permission_denied(update: Update) -> None:
    message = update.effective_message
    if message:
        await message.reply_text("⛔ Is command ki permission aapke liye OFF hai.")


async def admin_directory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not config.is_admin(user.id):
        await permission_denied(update)
        return
    await update.effective_message.reply_text(
        "🛡️ ADMIN CONTROL PANEL — COMMAND DIRECTORY\n\n"
        "Neeche button se directory aur Under Admin powers kholein.",
        reply_markup=_category_keyboard(),
    )


def register_admin_power_handlers(application: Application):
    application.add_handler(CommandHandler("adminalllist", admin_directory_command))
    application.add_handler(CallbackQueryHandler(
        admin_power_callback,
        pattern=r"^power:",
    ))
