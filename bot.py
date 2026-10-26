
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

from admin import register_admin_handlers
from api_accounts import register_api_handlers
from groups import (
    register_group_handlers,
    init_group_admin_schema,
)
from adminalllist import (
    adminalllist_command,
    admin_help_command,
)
from live_admin import register_live_admin_handlers
from live_campaigns import init_live_campaign_schema
from campaign_reports import register_campaign_report_handlers
from user import register_user_handlers


logger = logging.getLogger(__name__)


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
        user_record = await register_user(
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

    if user_record["status"] == "banned":
        await message.reply_text(
            "⛔ Your access has been disabled. "
            "Please contact the administrator."
        )
        return

    if user_record["status"] != "approved":
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
    query = update.callback_query

    if query is None or query.from_user is None:
        return

    await query.answer()

    telegram_id = query.from_user.id
    owner = is_admin(telegram_id)
    action = query.data or ""

    try:
        user_record = await get_user(telegram_id)
    except Exception:
        logger.exception("Could not load user.")
        if query.message:
            await query.message.reply_text(
                "⚠️ Database temporarily unavailable."
            )
        return

    if user_record is None:
        if query.message:
            await query.message.reply_text(
                "Please send /start to register first."
            )
        return

    if user_record["status"] == "banned":
        await query.edit_message_text(
            "⛔ Your account is disabled."
        )
        return

    if action == "admin_panel":
        if not owner:
            await query.edit_message_text(
                "⛔ Admin access required."
            )
            return

        await query.edit_message_text(
            "🛡️ Admin Panel\n\n"
            "Use /admin_help to view available commands.",
            reply_markup=admin_menu(),
        )
        return

    if action == "home":
        if user_record["status"] != "approved":
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

        await query.edit_message_text(
            "Admin commands:\n"
            "/admin_help\n"
            "/adminalllist\n"
            "/admin_stats\n"
            "/pending_users\n"
            "/approved_users\n"
            "/groups\n"
            "/all_services\n"
            "/campaign_report",
            reply_markup=admin_menu(),
        )
        return

    if user_record["status"] != "approved":
        await query.edit_message_text(
            "⏳ Please wait for admin approval."
        )
        return

    if action == "my_account":
        subscription = user_record["subscription_expires_at"]

        await query.edit_message_text(
            "👤 My Account\n\n"
            f"Name: {user_record['display_name'] or 'Not set'}\n"
            f"Username: @{user_record['username'] or 'Not set'}\n"
            f"Status: {user_record['status']}\n"
            f"Credits: {user_record['credits']}\n"
            f"Subscription expires: {subscription or 'Not set'}",
            reply_markup=main_menu(owner),
        )

    elif action == "my_credits":
        await query.edit_message_text(
            f"💳 Your balance: {user_record['credits']} credits",
            reply_markup=main_menu(owner),
        )

    elif action == "my_tasks":
        await query.edit_message_text(
            "📋 Task management is not connected to this menu yet.",
            reply_markup=main_menu(owner),
        )

    elif action == "invite_links":
        await query.edit_message_text(
            "🔗 Use the authorized group commands or contact "
            "the administrator to manage invitation links.",
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


async def post_init(application: Application) -> None:
    """Initialize existing database and additive schemas in order."""
    await init_db()

    # Must run before live campaign settings use groups.service_active.
    await init_group_admin_schema()
    await init_live_campaign_schema()

    logger.info("Database and admin schemas initialized.")

    for admin_id in ADMIN_IDS:
        logger.info("Configured admin ID: %s", admin_id)


async def post_shutdown(application: Application) -> None:
    """Close database connections gracefully."""
    await close_db()


def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Core commands
    application.add_handler(
        CommandHandler("start", start_command)
    )
    application.add_handler(
        CommandHandler("adminalllist", adminalllist_command)
    )
    application.add_handler(
        CommandHandler("admin_help", admin_help_command)
    )

    # Admin, API and group commands
    register_admin_handlers(application)
    register_api_handlers(application)
    register_group_handlers(application)

    # Quantity and service controls
    register_live_admin_handlers(application)
    register_campaign_report_handlers(application)

    # User panel callbacks (such as usr:...)
    register_user_handlers(application)

    # Keep the general callback handler last so that specific
    # callback handlers can process their own callback patterns.
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
