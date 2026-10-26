
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS, is_admin
from database import (
    init_db,
    close_db,
    register_user,
    get_user,
)

from quantity_admin import (
    init_quantity_schema,
    register_quantity_handlers,
)

logger = logging.getLogger(__name__)


# =========================
# MAIN MENU
# =========================

def main_menu(is_owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="my_account",
            ),
            InlineKeyboardButton(
                "📋 My Tasks",
                callback_data="my_tasks",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔗 Invite Links",
                callback_data="invite_links",
            ),
            InlineKeyboardButton(
                "💳 My Credits",
                callback_data="my_credits",
            ),
        ],
        [
            InlineKeyboardButton(
                "🆘 Contact Admin",
                callback_data="support",
            ),
        ],
    ]

    if is_owner:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    "🛡️ Admin Panel",
                    callback_data="admin_panel",
                ),
            ],
        )

    return InlineKeyboardMarkup(rows)


# =========================
# ADMIN MENU
# =========================

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👥 Pending Users",
                    callback_data="admin_pending",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 User Statistics",
                    callback_data="admin_stats",
                ),
                InlineKeyboardButton(
                    "📋 Task Queue",
                    callback_data="admin_tasks",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 Main Menu",
                    callback_data="home",
                ),
            ],
        ]
    )


# =========================
# START COMMAND
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
        logger.exception("Could not register Telegram user.")

        await message.reply_text(
            "⚠️ Registration is temporarily unavailable. "
            "Please try again later."
        )
        return

    if user["status"] == "banned":
        await message.reply_text(
            "⛔ Your access has been disabled. "
            "Please contact the administrator."
        )
        return

    if user["status"] != "approved":
        await message.reply_text(
            "👋 Welcome!\n\n"
            "Your registration has been received. "
            "Please wait for admin approval."
        )
        return

    await message.reply_text(
        f"👋 Welcome, {telegram_user.first_name}!\n\n"
        "Choose an option below:",
        reply_markup=main_menu(owner),
    )


# =========================
# BUTTON HANDLER
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
        logger.exception("Could not load user.")

        if query.message:
            await query.message.reply_text(
                "⚠️ Database temporarily unavailable."
            )
        return

    if user is None:
        if query.message:
            await query.message.reply_text(
                "Please send /start to register first."
            )
        return

    if user["status"] == "banned":
        await query.edit_message_text(
            "⛔ Your account is disabled."
        )
        return

    # Admin panel
    if action == "admin_panel":
        if not owner:
            await query.edit_message_text(
                "⛔ You are not authorized to access the admin panel."
            )
            return

        await query.edit_message_text(
            "🛡️ Admin Panel\n\n"
            "Select an administration option:",
            reply_markup=admin_menu(),
        )
        return

    # Return to home
    if action == "home":
        if user["status"] != "approved":
            await query.edit_message_text(
                "⏳ Your account is awaiting admin approval."
            )
            return

        await query.edit_message_text(
            "🏠 Main Menu\n\nChoose an option:",
            reply_markup=main_menu(owner),
        )
        return

    # Admin menu buttons
    if action.startswith("admin_"):
        if not owner:
            await query.edit_message_text(
                "⛔ Admin access required."
            )
            return

        await query.edit_message_text(
            "This admin feature needs its dedicated handler "
            "to be connected.",
            reply_markup=admin_menu(),
        )
        return

    # Non-approved users cannot access normal features
    if user["status"] != "approved":
        await query.edit_message_text(
            "⏳ Please wait for admin approval."
        )
        return

    # Account details
    if action == "my_account":
        subscription = user["subscription_expires_at"]

        await query.edit_message_text(
            "👤 My Account\n\n"
            f"Name: {user['display_name'] or 'Not set'}\n"
            f"Username: @{user['username'] or 'Not set'}\n"
            f"Status: {user['status']}\n"
            f"Credits: {user['credits']}\n"
            f"Subscription expires: {subscription or 'Not set'}",
            reply_markup=main_menu(owner),
        )

    # Credits
    elif action == "my_credits":
        await query.edit_message_text(
            f"💳 Your balance: {user['credits']} credits",
            reply_markup=main_menu(owner),
        )

    # Tasks
    elif action == "my_tasks":
        await query.edit_message_text(
            "📋 Your tasks will appear here once the "
            "task management module is connected.",
            reply_markup=main_menu(owner),
        )

    # Invite links
    elif action == "invite_links":
        await query.edit_message_text(
            "🔗 Invite Links\n\n"
            "Use this section to request or manage authorized "
            "community invitation links.",
            reply_markup=main_menu(owner),
        )

    # Support
    elif action == "support":
        await query.edit_message_text(
            "🆘 For support, contact the bot administrator.",
            reply_markup=main_menu(owner),
        )

    else:
        await query.edit_message_text(
            "Unknown option. Please return to the main menu.",
            reply_markup=main_menu(owner),
        )


# =========================
# DATABASE INITIALIZATION
# =========================

async def post_init(application: Application) -> None:
    logger.info("Initializing database...")

    # Existing database initialization
    await init_db()

    # Add quantity/service columns if missing
    await init_quantity_schema()

    logger.info("Database and quantity schema are ready.")

    for admin_id in ADMIN_IDS:
        logger.info(
            "Configured admin Telegram ID: %s",
            admin_id,
        )


# =========================
# DATABASE SHUTDOWN
# =========================

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

    # Start command
    application.add_handler(
        CommandHandler("start", start_command)
    )

    # Quantity management commands
    register_quantity_handlers(application)

    # Inline keyboard buttons
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    logger.info("Starting Telegram Community Manager.")

    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
