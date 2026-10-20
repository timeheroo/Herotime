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

from config import is_admin
from database import (
    get_pool,
    list_users,
    set_user_status,
    audit_action,
)

logger = logging.getLogger(name)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⏳ Pending Users",
                callback_data="adm:pending",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Approved Users",
                callback_data="adm:approved",
            ),
            InlineKeyboardButton(
                "🚫 Banned Users",
                callback_data="adm:banned",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="adm:stats",
            ),
        ],
    ])


def user_actions_keyboard(user_id: int, status: str):
    buttons = []

    if status == "pending":
        buttons.append([
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"adm:approve:{user_id}",
            ),
            InlineKeyboardButton(
                "🚫 Ban",
                callback_data=f"adm:ban:{user_id}",
            ),
        ])
    elif status == "approved":
        buttons.append([
            InlineKeyboardButton(
                "🚫 Ban",
                callback_data=f"adm:ban:{user_id}",
            ),
        ])
    elif status == "banned":
        buttons.append([
            InlineKeyboardButton(
                "♻️ Restore Access",
                callback_data=f"adm:approve:{user_id}",
            ),
        ])

    return InlineKeyboardMarkup(buttons)


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Open the owner-only admin panel."""
    telegram_user = update.effective_user
    message = update.effective_message

    if telegram_user is None or message is None:
        return

    if not is_admin(telegram_user.id):
        await message.reply_text(
            "⛔ You are not authorized to access this panel."
        )
        return

    await message.reply_text(
        "🛡️ Admin Panel\n\nChoose an option:",
        reply_markup=admin_keyboard(),
    )


async def show_users(
    query,
    status: str,
):
    """Display users with the requested status."""
    users = await list_users(status=status, limit=20)

    if not users:
        await query.edit_message_text(
            f"No users found with status: {status}",
            reply_markup=admin_keyboard(),
        )
        return

    await query.edit_message_text(
        f"👥 Users — {status.title()}\n\n"
        "Select a user below:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{u['display_name'] or u['telegram_id']} "
                    f"(ID {u['id']})",
                    callback_data=f"adm:view:{u['id']}",
                )
            ]
            for u in users
        ] + [[
            InlineKeyboardButton(
                "🔙 Admin Menu",
                callback_data="adm:home",
            )
        ]]),
    )


async def show_user(query, user_id: int):
    """Show a user's profile and available admin actions."""
    pool = get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, telegram_id, username, display_name,
                   role, status, credits, created_at,
                   subscription_expires_at
            FROM users
            WHERE id = $1
            """,
            user_id,
        )

    if user is None:
        await query.edit_message_text(
            "User not found.",
            reply_markup=admin_keyboard(),
        )
        return

    await query.edit_message_text(
        "👤 User Details\n\n"
        f"Database ID: {user['id']}\n"
        f"Telegram ID: {user['telegram_id']}\n"
        f"Name: {user['display_name'] or 'Not set'}\n"
        f"Username: @{user['username'] or 'Not set'}\n"
        f"Role: {user['role']}\n"
        f"Status: {user['status']}\n"
        f"Credits: {user['credits']}\n"
        f"Joined: {user['created_at']}",
        reply_markup=user_actions_keyboard(
            user["id"], user["status"]
        ),
    )


async def show_statistics(query):
    """Display basic user and task statistics."""
    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE status = 'pending'
                ) AS pending,
                COUNT(*) FILTER (
                    WHERE status = 'approved'
                ) AS approved,
                COUNT(*) FILTER (
                    WHERE status = 'banned'
                ) AS banned
            FROM users
            """
        )

        tasks = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE status IN ('queued', 'running', 'paused')
                ) AS active
            FROM tasks
            """
        )

    await query.edit_message_text(
        "📊 Admin Statistics\n\n"
        f"Total users: {users['total']}\n"
        f"Pending: {users['pending']}\n"
        f"Approved: {users['approved']}\n"
        f"Banned: {users['banned']}\n\n"
        f"Total tasks: {tasks['total']}\n"
        f"Active tasks: {tasks['active']}",
        reply_markup=admin_keyboard(),
    )


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Process owner-only admin menu callbacks."""
    query = update.callback_query

    if query is None:
        return

    # Check permissions before performing any action.
    if not is_admin(query.from_user.id):
        await query.answer(
            "You are not authorized.",
            show_alert=True,
        )
        return

    await query.answer()

    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "home":
            await query.edit_message_text(
                "🛡️ Admin Panel",
                reply_markup=admin_keyboard(),
            )

        elif action in {"pending", "approved", "banned"}:
            await show_users(query, action)

        elif action == "view" and len(parts) == 3:
            await show_user(query, int(parts[2]))

        elif action in {"approve", "ban"} and len(parts) == 3:
            user_id = int(parts[2])

            pool = get_pool()

            async with pool.acquire() as conn:
                target = await conn.fetchrow(
                    """
                    SELECT id, telegram_id, role, status
                    FROM users
                    WHERE id = $1
                    """,
                    user_id,
                )

            if target is None:
                await query.edit_message_text("User not found.")
                return

            # Never allow an admin to disable an owner account.
            if target["role"] == "admin":
                await query.edit_message_text(
                    "Admin accounts cannot be changed here.",
                    reply_markup=admin_keyboard(),
                )
                return

            new_status = (
                "approved" if action == "approve" else "banned"
            )

            updated = await set_user_status(
                user_id, new_status
            )

            if updated is None:
                await query.edit_message_text("User not found.")
                return

            await audit_action(
                actor_user_id=None,
                action=f"user_{new_status}",
                details={
                    "target_user_id": user_id,
                    "target_telegram_id": target["telegram_id"],
                },
            )

await query.edit_message_text(
                f"✅ User status updated to: {new_status}",
                reply_markup=admin_keyboard(),
            )

        elif action == "stats":
            await show_statistics(query)

        else:
            await query.edit_message_text(
                "Unknown admin action.",
                reply_markup=admin_keyboard(),
            )

    except (ValueError, TypeError):
        await query.edit_message_text(
            "Invalid request.",
            reply_markup=admin_keyboard(),
        )
    except Exception:
        logger.exception("Admin callback failed.")
        await query.edit_message_text(
            "⚠️ Could not complete the operation.",
            reply_markup=admin_keyboard(),
        )


def register_admin_handlers(application):
    """Register admin commands and callbacks."""
    application.add_handler(
        CommandHandler("admin", admin_command)
    )
    application.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^adm:",
        )
    )
