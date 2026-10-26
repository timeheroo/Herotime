
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS, is_admin
from database import init_db, close_db, register_user, get_user

from quantity_admin import (
    init_quantity_schema,
    register_quantity_handlers,
)

from groups import (
    init_group_admin_schema,
    register_group_handlers,
)

logger = logging.getLogger(__name__)


# =========================
# MENUS
# =========================

def main_menu(is_owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("👤 My Account", callback_data="my_account"),
            InlineKeyboardButton("📋 My Tasks", callback_data="my_tasks"),
        ],
        [
            InlineKeyboardButton("🔗 Invite Links", callback_data="invite_links"),
            InlineKeyboardButton("💳 My Credits", callback_data="my_credits"),
        ],
        [
            InlineKeyboardButton("🆘 Contact Admin", callback_data="support"),
        ],
    ]

    if is_owner:
        rows.insert(
            0,
            [InlineKeyboardButton("🛡️ Admin Panel", callback_data="admin_panel")],
        )

    return InlineKeyboardMarkup(rows)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 CHANNELS LIST", callback_data="admin_channels")],
        [InlineKeyboardButton("🔑 API ID / API HASH LIST", callback_data="admin_api_list")],
        [InlineKeyboardButton("🛡️ ALL POWER LIST", callback_data="admin_all_power")],
        [InlineKeyboardButton("📊 REPORT", callback_data="admin_report")],
        [InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")],
    ])


def admin_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="admin_panel")],
        [InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")],
    ])


# =========================
# START
# =========================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    telegram_user = update.effective_user
    message = update.effective_message

    if telegram_user is None or message is None:
        return

    owner = is_admin(telegram_user.id)

    try:
        user = await register_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            display_name=telegram_user.full_name,
            is_admin=owner,
        )
    except Exception:
        logger.exception("User registration failed")
        await message.reply_text(
            "⚠️ Registration temporarily unavailable. Please try again."
        )
        return

    if user["status"] == "banned":
        await message.reply_text("⛔ Your account is disabled.")
        return

    if user["status"] != "approved":
        await message.reply_text(
            "👋 Welcome!\n\nRegistration received. Please wait for admin approval."
        )
        return

    await message.reply_text(
        f"👋 Welcome, {telegram_user.first_name}!\n\nChoose an option:",
        reply_markup=main_menu(owner),
    )


# =========================
# INLINE BUTTONS
# =========================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    if query is None or query.from_user is None:
        return

    await query.answer()

    telegram_id = query.from_user.id
    owner = is_admin(telegram_id)
    action = query.data or ""

    try:
        user = await get_user(telegram_id)
    except Exception:
        logger.exception("Could not load user")
        if query.message:
            await query.message.reply_text(
                "⚠️ Database temporarily unavailable."
            )
        return

    if user is None:
        if query.message:
            await query.message.reply_text("Please send /start first.")
        return

    if user["status"] == "banned":
        await query.edit_message_text("⛔ Your account is disabled.")
        return

    if action == "admin_panel":
        if not owner:
            await query.edit_message_text("⛔ Admin access required.")
            return

        await query.edit_message_text(
            "🛡️ ADMIN PANEL\n\nSelect an option:",
            reply_markup=admin_menu(),
        )
        return

    if action == "home":
        if user["status"] != "approved":
            await query.edit_message_text(
                "⏳ Your account is awaiting admin approval."
            )
            return

        await query.edit_message_text(
            "🏠 MAIN MENU\n\nChoose an option:",
            reply_markup=main_menu(owner),
        )
        return

    admin_pages = {
        "admin_channels": (
            "📂 CHANNELS LIST\n\n"
            "Use /groups to list saved channels.\n"
            "Use /add_group @username source or target to add one."
        ),
        "admin_api_list": (
            "🔑 API ID / API HASH LIST\n\n"
            "API record management is not connected yet."
        ),
        "admin_all_power": (
            "🛡️ ALL POWER LIST\n\n"
            "Individual admin permission management is not connected yet."
        ),
        "admin_report": (
            "📊 REPORT\n\n"
            "Reporting module is not connected yet."
        ),
    }

    if action in admin_pages:
        if not owner:
            await query.edit_message_text("⛔ Admin access required.")
            return

        await query.edit_message_text(
            admin_pages[action],
            reply_markup=admin_back_menu(),
        )
        return

    if action.startswith("admin_"):
        if not owner:
            await query.edit_message_text("⛔ Admin access required.")
            return

        await query.edit_message_text(
            "This admin feature is not connected yet.",
            reply_markup=admin_back_menu(),
        )
        return

    if user["status"] != "approved":
        await query.edit_message_text(
            "⏳ Please wait for admin approval."
        )
        return

    if action == "my_account":
        subscription = user["subscription_expires_at"]
        await query.edit_message_text(
            "👤 MY ACCOUNT\n\n"
            f"Name: {user['display_name'] or 'Not set'}\n"
            f"Username: @{user['username'] or 'Not set'}\n"
            f"Status: {user['status']}\n"
            f"Credits: {user['credits']}\n"
            f"Subscription expires: {subscription or 'Not set'}",
            reply_markup=main_menu(owner),
        )

    elif action == "my_credits":
        await query.edit_message_text(
            f"💳 Your balance: {user['credits']} credits",
            reply_markup=main_menu(owner),
        )

    elif action == "my_tasks":
        await query.edit_message_text(
            "📋 Your tasks will appear here when the task module is connected.",
            reply_markup=main_menu(owner),
        )

    elif action == "invite_links":
        await query.edit_message_text(
            "🔗 Invite Links\n\n"
            "Use this section to request authorized community invitation links.",
            reply_markup=main_menu(owner),
        )

    elif action == "support":
        await query.edit_message_text(
            "🆘 Please contact the bot administrator for support.",
            reply_markup=main_menu(owner),
        )

    else:
        await query.edit_message_text(
            "Unknown option. Please return to the main menu.",
            reply_markup=main_menu(owner),
        )


# =========================
# DATABASE STARTUP
# =========================

async def post_init(application: Application) -> None:
    logger.info("Initializing database...")

    await init_db()
    await init_quantity_schema()
    await init_group_admin_schema()

    logger.info("Database and group/quantity schemas are ready.")

    for admin_id in ADMIN_IDS:
        logger.info("Configured owner Telegram ID: %s", admin_id)


async def post_shutdown(application: Application) -> None:
    logger.info("Closing database connections...")
    await close_db()
    logger.info("Database connections closed.")


# =========================
# MAIN
# =========================

def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))

    # Quantity commands
    register_quantity_handlers(application)

    # Channel/group commands
    register_group_handlers(application)

    # Inline buttons
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Starting Telegram Community Manager.")

    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
