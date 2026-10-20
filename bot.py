import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
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

logger = logging.getLogger(name)


def main_menu(is_owner: bool) -> InlineKeyboardMarkup:
    """Build the main menu keyboard."""
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


def admin_menu() -> InlineKeyboardMarkup:
    """Build the owner-only administration menu."""
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


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Register the user and show the appropriate menu."""
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


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline keyboard callbacks."""
    query = update.callback_query

    if query is None or query.from_user is None:
        return

    await query.answer()

    telegram_id = query.from_user.id
    owner = is_admin(telegram_id)
    action = query.data

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
        await query.edit_message_text(
            "⛔ Your account is disabled."
        )
        return

    if action == "admin_panel":
        if not owner:
            await query.edit_message_text(
                "⛔ You are not authorized to access the admin panel."
            )
            return

        await query.edit_message_text(
            "🛡️ Admin Panel\n\nSelect an administration option:",
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
            "🏠 Main Menu\n\nChoose an option:",
            reply_markup=main_menu(owner),
        )
        return

    if action.startswith("admin_"):
        if not owner:
            await query.edit_message_text(
                "⛔ Admin access required."
            )
            return

        # The dedicated admin module will implement these actions.
        await query.edit_message_text(
            "This admin feature will be connected in the next files.",
            reply_markup=admin_menu(),
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
            "👤 My Account\n\n"
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
            "📋 Your tasks will appear here once the task "
            "management module is connected.",
            reply_markup=main_menu(owner),
        )

    elif action == "invite_links":
        await query.edit_message_text(
            "🔗 Invite Links\n\n"
            "Use this section to request or manage authorized "
            "community invitation links.",
            reply_markup=main_menu(owner),
        )

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


async def post_init(application: Application) -> None:
    """Initialize the database before accepting updates."""
    await init_db()
    logger.info("Database ready. Bot is starting.")

    # Register configured admins in the database.
    # They still need to send /start to create their profile.
    for admin_id in ADMIN_IDS:
        logger.info("Configured owner Telegram ID: %s", admin_id)


async def post_shutdown(application: Application) -> None:
    """Close database connections gracefully."""
    await close_db()


def main() -> None:
    """Create and run the Telegram bot."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

application.add_handler(
        CommandHandler("start", start_command)
    )
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    logger.info("Starting Telegram Community Manager.")

    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )


if name == "main":
    main()
