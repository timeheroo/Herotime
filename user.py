import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from database import get_user, get_pool

logger = logging.getLogger(name)


def user_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="usr:account",
            ),
            InlineKeyboardButton(
                "💳 My Credits",
                callback_data="usr:credits",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 My Tasks",
                callback_data="usr:tasks",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔗 Community Invite Links",
                callback_data="usr:invites",
            ),
        ],
        [
            InlineKeyboardButton(
                "🆘 Support",
                callback_data="usr:support",
            ),
        ],
    ])


async def user_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Open the user panel."""
    telegram_user = update.effective_user
    message = update.effective_message

    if telegram_user is None or message is None:
        return

    user = await get_user(telegram_user.id)

    if user is None:
        await message.reply_text(
            "Please send /start first to register."
        )
        return

    if user["status"] == "banned":
        await message.reply_text(
            "⛔ Your account access has been disabled."
        )
        return

    if user["status"] != "approved":
        await message.reply_text(
            "⏳ Your account is awaiting admin approval."
        )
        return

    await message.reply_text(
        "👋 Welcome to your User Panel!\n\n"
        "Choose an option:",
        reply_markup=user_menu(),
    )


async def get_user_tasks(telegram_id: int):
    """Fetch the latest tasks belonging to this user."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.task_type, t.status,
                   t.total_count, t.processed_count,
                   t.error_count, t.created_at
            FROM tasks AS t
            JOIN users AS u
              ON u.id = t.owner_user_id
            WHERE u.telegram_id = $1
            ORDER BY t.created_at DESC
            LIMIT 10
            """,
            telegram_id,
        )

    return [dict(row) for row in rows]


async def user_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle user panel actions."""
    query = update.callback_query

    if query is None:
        return

    await query.answer()

    telegram_id = query.from_user.id

    try:
        user = await get_user(telegram_id)

        if user is None:
            await query.edit_message_text(
                "Please send /start first to register."
            )
            return

        if user["status"] == "banned":
            await query.edit_message_text(
                "⛔ Your account access has been disabled."
            )
            return

        if user["status"] != "approved":
            await query.edit_message_text(
                "⏳ Your account is awaiting admin approval."
            )
            return

        action = (query.data or "").split(":", 1)[-1]

        if action == "account":
            await query.edit_message_text(
                "👤 My Account\n\n"
                f"Name: {user['display_name'] or 'Not set'}\n"
                f"Username: @{user['username'] or 'Not set'}\n"
                f"Status: {user['status']}\n"
                f"Credits: {user['credits']}\n"
                f"Subscription expires: "
                f"{user['subscription_expires_at'] or 'Not set'}",
                reply_markup=user_menu(),
            )

        elif action == "credits":
            await query.edit_message_text(
                f"💳 Available credits: {user['credits']}\n\n"
                "For credit top-ups, please contact the administrator.",
                reply_markup=user_menu(),
            )

        elif action == "tasks":
            tasks = await get_user_tasks(telegram_id)

            if not tasks:
                await query.edit_message_text(
                    "📋 You don't have any tasks yet.",
                    reply_markup=user_menu(),
                )
                return

            lines = ["📋 Your Recent Tasks\n"]

            for task in tasks:
                lines.append(
                    f"Task #{task['id']}\n"
                    f"Type: {task['task_type']}\n"
                    f"Status: {task['status']}\n"
                    f"Progress: {task['processed_count']}/"
                    f"{task['total_count']}\n"
                    f"Errors: {task['error_count']}\n"
                )

            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=user_menu(),
            )

        elif action == "invites":
            await query.edit_message_text(
                "🔗 Community Invite Links\n\n"
                "Invite links can be requested for communities "
                "you are authorized to manage. Members choose "
                "whether to join voluntarily.\n\n"
                "Please contact support to request a link.",
                reply_markup=user_menu(),
            )

        elif action == "support":
            await query.edit_message_text(
                "🆘 Support\n\n"
                "Use /start to return to the main menu or "
                "contact the administrator directly.",
                reply_markup=user_menu(),
            )

        else:
            await query.edit_message_text(
                "Unknown option.",
                reply_markup=user_menu(),
            )

    except Exception:
        logger.exception("User panel callback failed.")
        await query.edit_message_text(
            "⚠️ Unable to load this information. Please try again."
        )


def register_user_handlers(application):
    """Register user panel commands and callbacks."""
    application.add_handler(
        CommandHandler("panel", user_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            user_callback,
            pattern=r"^usr:",
        )
    )
