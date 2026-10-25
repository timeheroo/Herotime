import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, TelegramError
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
from notifications import init_notification_schema
from live_campaigns import init_live_campaign_schema
from live_admin import register_live_admin_handlers
from campaign_reports import register_campaign_report_handlers


logger = logging.getLogger(__name__)


# --------------------------------------------------
# SAFE TELEGRAM MESSAGE EDIT
# --------------------------------------------------

async def safe_edit_message_text(
    query,
    text: str,
    **kwargs,
) -> None:
    """Edit a callback message safely."""
    try:
        await query.edit_message_text(
            text=text,
            **kwargs,
        )
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            logger.debug(
                "Telegram message was already up to date."
            )
            return
        raise


# --------------------------------------------------
# MAIN MENU
# --------------------------------------------------

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


# --------------------------------------------------
# ADMIN MENU
# --------------------------------------------------

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
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
    ])


# --------------------------------------------------
# /START
# --------------------------------------------------

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


# --------------------------------------------------
# INLINE BUTTON HANDLER
# --------------------------------------------------

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
        await query.message.reply_text(
            "⚠️ Database temporarily unavailable."
        )
        return

    if user is None:
        await query.message.reply_text(
            "Please send /start to register first."
        )
        return

    if user["status"] == "banned":
        await safe_edit_message_text(
            query,
            "⛔ Your account is disabled.",
        )
        return

    # Admin panel
    if action == "admin_panel":
        if not owner:
            await safe_edit_message_text(
                query,
                "⛔ You are not authorized to access "
                "the admin panel.",
            )
            return

        await safe_edit_message_text(
            query,
            "🛡️ Admin Panel\n\n"
            "Select an administration option:",
            reply_markup=admin_menu(),
        )
        return

    # Return to home
    if action == "home":
        if user["status"] != "approved":
            await safe_edit_message_text(
                query,
                "⏳ Your account is awaiting admin approval.",
            )
            return

        await safe_edit_message_text(
            query,
            "🏠 Main Menu\n\nChoose an option:",
            reply_markup=main_menu(owner),
        )
        return

    # Existing admin menu buttons
    if action.startswith("admin_"):
        if not owner:
            await safe_edit_message_text(
                query,
                "⛔ Admin access required.",
            )
            return

        await safe_edit_message_text(
            query,
            "This admin menu option is not connected yet.\n\n"
            "Use the available admin commands.",
            reply_markup=admin_menu(),
        )
        return

    if user["status"] != "approved":
        await safe_edit_message_text(
            query,
            "⏳ Please wait for admin approval.",
        )
        return

    if action == "my_account":
        subscription = user["subscription_expires_at"]

        await safe_edit_message_text(
            query,
            "👤 My Account\n\n"
            f"Name: {user['display_name'] or 'Not set'}\n"
            f"Username: @{user['username'] or 'Not set'}\n"
            f"Status: {user['status']}\n"
            f"Credits: {user['credits']}\n"
            f"Subscription expires: {subscription or 'Not set'}",
            reply_markup=main_menu(owner),
        )

    elif action == "my_credits":
        await safe_edit_message_text(
            query,
            f"💳 Your balance: {user['credits']} credits",
            reply_markup=main_menu(owner),
        )

    elif action == "my_tasks":
        await safe_edit_message_text(
            query,
            "📋 Your tasks will appear here once the task "
            "management module is connected.",
            reply_markup=main_menu(owner),
        )

    elif action == "invite_links":
        await safe_edit_message_text(
            query,
            "🔗 Invite Links\n\n"
            "Use this section to request or manage authorized "
            "community invitation links.",
            reply_markup=main_menu(owner),
        )

    elif action == "support":
        await safe_edit_message_text(
            query,
            "🆘 For support, contact the bot administrator.",
            reply_markup=main_menu(owner),
        )

    else:
        await safe_edit_message_text(
            query,
            "Unknown option. Please return to the main menu.",
            reply_markup=main_menu(owner),
        )


# --------------------------------------------------
# ERROR HANDLER
# --------------------------------------------------

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    error = context.error

    if isinstance(error, TelegramError):
        logger.error("Telegram error: %s", error)
    else:
        logger.error(
            "Unexpected application error.",
            exc_info=error,
        )


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

async def post_init(application: Application) -> None:
    """Initialize database schemas before bot starts."""
    await init_db()
    logger.info("Database initialized.")

    await init_notification_schema()
    logger.info("Notification schema initialized.")

    await init_live_campaign_schema()
    logger.info("Live campaign schema initialized.")

    for admin_id in ADMIN_IDS:
        logger.info(
            "Configured owner Telegram ID: %s",
            admin_id,
        )


async def post_shutdown(application: Application) -> None:
    """Close database connections."""
    await close_db()
    logger.info("Database connections closed.")


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Basic command
    application.add_handler(
        CommandHandler("start", start_command)
    )

    # Register live campaign admin commands
    register_live_admin_handlers(application)

    # Register campaign reports
    register_campaign_report_handlers(application)

    # General callback handler comes after dedicated handlers
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # Log unexpected errors
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram Community Manager.")

    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
