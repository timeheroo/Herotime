"""Admin handlers compatible with the current config.py and database.py.

Commands implemented here:
  /admin
  /admin_stats
  /pending_users
  /approved_users
  /approve_user TELEGRAM_ID
  /ban_user TELEGRAM_ID
  /unban_user TELEGRAM_ID
  /user_info TELEGRAM_ID
  /add_credit TELEGRAM_ID AMOUNT REASON
  /deduct_credit TELEGRAM_ID AMOUNT REASON
  /credit_balance TELEGRAM_ID
  /credit_history TELEGRAM_ID
  /audit_logs

Note: handlers still must be registered in bot.py. /adminalllist is in
adminalllist.py and must also be registered in bot.py.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import is_admin
import database

logger = logging.getLogger(__name__)


async def _require_admin(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return False
    if not is_admin(user.id):
        await message.reply_text("⛔ Access denied. Yeh command sirf admin ke liye hai.")
        return False
    return True


async def _find_user_by_telegram_id(telegram_id: int):
    async with database.connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            telegram_id,
        )
    return dict(row) if row else None


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    await update.effective_message.reply_text(
        "🛡️ Admin Control Panel\n\n"
        "/adminalllist — Saari admin commands aur unka kaam\n"
        "/admin_stats — User/task statistics\n"
        "/pending_users — Pending users\n"
        "/approved_users — Approved users\n"
        "/approve_user TELEGRAM_ID — Approve user\n"
        "/ban_user TELEGRAM_ID — Ban user\n"
        "/unban_user TELEGRAM_ID — Unban user\n"
        "/user_info TELEGRAM_ID — User details\n"
        "/add_credit TELEGRAM_ID AMOUNT REASON — Add credits\n"
        "/deduct_credit TELEGRAM_ID AMOUNT REASON — Deduct credits\n"
        "/credit_balance TELEGRAM_ID — Check credits\n"
        "/credit_history TELEGRAM_ID — Credit history\n"
        "/audit_logs — Recent admin actions"
    )


async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    try:
        async with database.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)::int AS total_users,
                    COUNT(*) FILTER (WHERE status = 'pending')::int AS pending_users,
                    COUNT(*) FILTER (WHERE status = 'approved')::int AS approved_users,
                    COUNT(*) FILTER (WHERE status = 'banned')::int AS banned_users,
                    COALESCE(SUM(credits), 0)::bigint AS total_credits
                FROM users
                """
            )
            task_row = await conn.fetchrow(
                """
                SELECT COUNT(*)::int AS total_tasks,
                       COUNT(*) FILTER (WHERE status IN ('queued','running','paused'))::int AS active_tasks
                FROM tasks
                """
            )
        await update.effective_message.reply_text(
            "📊 ADMIN STATS\n"
            f"Total users: {row['total_users']}\n"
            f"Pending: {row['pending_users']}\n"
            f"Approved: {row['approved_users']}\n"
            f"Banned: {row['banned_users']}\n"
            f"Total credits: {row['total_credits']}\n"
            f"Total tasks: {task_row['total_tasks']}\n"
            f"Queued/running/paused tasks: {task_row['active_tasks']}"
        )
    except Exception:
        logger.exception("Failed to load admin stats")
        await update.effective_message.reply_text("⚠️ Stats load nahi hue. Logs check karein.")


async def _list_users_command(update: Update, status: str, title: str) -> None:
    if not await _require_admin(update):
        return
    try:
        users = await database.list_users(status=status, limit=50)
        if not users:
            await update.effective_message.reply_text(f"{title}\nKoi user nahi mila.")
            return
        lines = [title, ""]
        for user in users:
            username = f"@{user['username']}" if user.get("username") else "(no username)"
            lines.append(
                f"DB ID: {user['id']} | Telegram ID: {user['telegram_id']}\n"
                f"{username} | status: {user['status']} | credits: {user['credits']}"
            )
        await update.effective_message.reply_text("\n".join(lines)[:3900])
    except Exception:
        logger.exception("Failed to list users")
        await update.effective_message.reply_text("⚠️ User list load nahi hui. Logs check karein.")


async def pending_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_command(update, "pending", "⏳ PENDING USERS")


async def approved_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_command(update, "approved", "✅ APPROVED USERS")


async def _set_user_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str) -> None:
    if not await _require_admin(update):
        return
    message = update.effective_message
    if not context.args:
        await message.reply_text(f"Usage: /{ 'approve_user' if status == 'approved' else 'ban_user' if status == 'banned' else 'unban_user' } TELEGRAM_ID")
        return
    try:
        telegram_id = int(context.args[0])
        user = await _find_user_by_telegram_id(telegram_id)
        if not user:
            await message.reply_text("❌ Is Telegram ID ka user database mein nahi mila.")
            return
        if user["role"] == "admin" and status != "approved":
            await message.reply_text("⛔ Configured admin ko is command se ban nahi kar sakte.")
            return
        result = await database.set_user_status(user["id"], status)
        if not result:
            await message.reply_text("❌ User status update nahi hua.")
            return
        await database.audit_action(
            actor_user_id=None,
            action=f"user_status_{status}",
            details={"target_telegram_id": telegram_id},
        )
        await message.reply_text(f"✅ User {telegram_id} ka status: {status}")
    except ValueError:
        await message.reply_text("❌ Telegram ID number mein dein.")
    except Exception:
        logger.exception("Failed to update user status")
        await message.reply_text("⚠️ Status update nahi hua. Logs check karein.")


async def approve_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_user_status_command(update, context, "approved")


async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_user_status_command(update, context, "banned")


async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_user_status_command(update, context, "approved")


async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /user_info TELEGRAM_ID")
        return
    try:
        telegram_id = int(context.args[0])
        user = await _find_user_by_telegram_id(telegram_id)
        if not user:
            await update.effective_message.reply_text("❌ User nahi mila.")
            return
        await update.effective_message.reply_text(
            "👤 USER INFO\n"
            f"Telegram ID: {user['telegram_id']}\n"
            f"Username: @{user['username']}" if user.get("username") else
            "👤 USER INFO\n"
            f"Telegram ID: {user['telegram_id']}\nUsername: (none)"
        )
    except ValueError:
        await update.effective_message.reply_text("❌ Telegram ID number mein dein.")
    except Exception:
        logger.exception("Failed to load user info")
        await update.effective_message.reply_text("⚠️ User details load nahi hui.")


async def _credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE, sign: int) -> None:
    if not await _require_admin(update):
        return
    if len(context.args) < 3:
        command = "add_credit" if sign > 0 else "deduct_credit"
        await update.effective_message.reply_text(
            f"Usage: /{command} TELEGRAM_ID AMOUNT REASON\n"
            "Example: /{command} 123456789 10 manual_adjustment".replace("{command}", command)
        )
        return
    try:
        telegram_id = int(context.args[0])
        amount = int(context.args[1])
        reason = " ".join(context.args[2:]).strip()
        if amount <= 0:
            raise ValueError("Amount positive hona chahiye.")
        user = await _find_user_by_telegram_id(telegram_id)
        if not user:
            await update.effective_message.reply_text("❌ User nahi mila.")
            return
        result = await database.adjust_credits(user["id"], sign * amount, reason)
        await database.audit_action(
            actor_user_id=None,
            action="credits_adjusted",
            details={"target_telegram_id": telegram_id, "amount": sign * amount, "reason": reason},
        )
        await update.effective_message.reply_text(
            f"✅ Credits update hue. Telegram ID: {telegram_id}\nNew balance: {result['credits']}"
        )
    except ValueError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
    except Exception:
        logger.exception("Failed to adjust credits")
        await update.effective_message.reply_text("⚠️ Credits update nahi hue. Logs check karein.")


async def add_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _credit_command(update, context, 1)


async def deduct_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _credit_command(update, context, -1)


async def credit_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /credit_balance TELEGRAM_ID")
        return
    try:
        telegram_id = int(context.args[0])
        user = await _find_user_by_telegram_id(telegram_id)
        if not user:
            await update.effective_message.reply_text("❌ User nahi mila.")
            return
        await update.effective_message.reply_text(
            f"💳 Telegram ID: {telegram_id}\nCredits: {user['credits']}"
        )
    except ValueError:
        await update.effective_message.reply_text("❌ Telegram ID number mein dein.")


async def credit_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /credit_history TELEGRAM_ID")
        return
    try:
        telegram_id = int(context.args[0])
        async with database.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT ct.amount, ct.reason, ct.created_at
                FROM credit_transactions ct
                JOIN users u ON u.id = ct.user_id
                WHERE u.telegram_id = $1
                ORDER BY ct.created_at DESC
                LIMIT 20
                """,
                telegram_id,
            )
        if not rows:
            await update.effective_message.reply_text("Koi credit transaction nahi mila.")
            return
        lines = ["💳 CREDIT HISTORY"]
        for row in rows:
            lines.append(f"{row['created_at']:%Y-%m-%d %H:%M} | {row['amount']:+} | {row['reason']}")
        await update.effective_message.reply_text("\n".join(lines)[:3900])
    except ValueError:
        await update.effective_message.reply_text("❌ Telegram ID number mein dein.")
    except Exception:
        logger.exception("Failed to load credit history")
        await update.effective_message.reply_text("⚠️ Credit history load nahi hui.")


async def audit_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    try:
        async with database.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT action, details, created_at
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
        if not rows:
            await update.effective_message.reply_text("📋 Abhi audit logs nahi hain.")
            return
        lines = ["📋 RECENT AUDIT LOGS"]
        for row in rows:
            lines.append(f"{row['created_at']:%Y-%m-%d %H:%M} | {row['action']} | {row['details']}")
        await update.effective_message.reply_text("\n".join(lines)[:3900])
    except Exception:
        logger.exception("Failed to load audit logs")
        await update.effective_message.reply_text("⚠️ Audit logs load nahi hue.")


def register_admin_handlers(application) -> None:
    """Register handlers; call this once from bot.py."""
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("admin_stats", admin_stats_command))
    application.add_handler(CommandHandler("pending_users", pending_users_command))
    application.add_handler(CommandHandler("approved_users", approved_users_command))
    application.add_handler(CommandHandler("approve_user", approve_user_command))
    application.add_handler(CommandHandler("ban_user", ban_user_command))
    application.add_handler(CommandHandler("unban_user", unban_user_command))
    application.add_handler(CommandHandler("user_info", user_info_command))
    application.add_handler(CommandHandler("add_credit", add_credit_command))
    application.add_handler(CommandHandler("deduct_credit", deduct_credit_command))
    application.add_handler(CommandHandler("credit_balance", credit_balance_command))
    application.add_handler(CommandHandler("credit_history", credit_history_command))
    application.add_handler(CommandHandler("audit_logs", audit_logs_command))
