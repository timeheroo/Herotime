```python
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import has_permission

logger = logging.getLogger(__name__)

REPORT_WINDOWS = {
    "24h": ("Last 24 Hours", 24),
    "72h": ("Last 72 Hours", 72),
    "daily": ("Today (24 Hours)", 24),
    "weekly": ("Last 7 Days", 168),
    "monthly": ("Last 30 Days", 720),
}


async def report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "view_reports"):
        await message.reply_text(
            "❌ Aapko reports dekhne ki permission nahi hai."
        )
        return

    period = context.args[0].lower() if context.args else "24h"

    if period not in REPORT_WINDOWS:
        await message.reply_text(
            "Use:\n"
            "/report 24h\n"
            "/report 72h\n"
            "/report daily\n"
            "/report weekly\n"
            "/report monthly"
        )
        return

    label, hours = REPORT_WINDOWS[period]

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            activity_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM activity_logs
                WHERE created_at >= NOW() - ($1 * INTERVAL '1 hour')
                """,
                hours,
            )

            live_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM live_tasks
                WHERE created_at >= NOW() - ($1 * INTERVAL '1 hour')
                """,
                hours,
            )

            reaction_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM reaction_tasks
                WHERE created_at >= NOW() - ($1 * INTERVAL '1 hour')
                """,
                hours,
            )

            channel_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM channels
                WHERE is_active = TRUE
                """
            )

        await message.reply_text(
            f"📊 ACTIVITY REPORT\n"
            f"Period: {label}\n\n"
            f"📝 Recorded activities: {activity_count or 0}\n"
            f"📡 Live-task configurations created: {live_count or 0}\n"
            f"❤️ Reaction-task configurations created: {reaction_count or 0}\n"
            f"📢 Currently active channels/groups: {channel_count or 0}\n\n"
            "Note: Yeh database records hain, actual views, reactions ya spend ka measurement nahi."
        )

    except Exception:
        logger.exception("Failed to generate report")
        await message.reply_text(
            "❌ Report generate nahi hui. Database schema aur Railway logs check karein."
        )


async def recent_activity_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "view_reports"):
        await message.reply_text(
            "❌ Aapko activ
```
