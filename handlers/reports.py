
import logging
from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission

logger = logging.getLogger(__name__)

REPORT_WINDOWS = {
    "24h": timedelta(hours=24),
    "72h": timedelta(hours=72),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


async def _authorized(update: Update) -> bool:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return False

    allowed, reason = await require_permission(
        user.id,
        "view_reports",
    )

    if not allowed:
        await message.reply_text(reason)
        return False

    return True


async def report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    period = context.args[0].lower() if context.args else "24h"

    if period not in REPORT_WINDOWS:
        await message.reply_text(
            "Usage:\n"
            "/report 24h\n"
            "/report 72h\n"
            "/report daily\n"
            "/report weekly\n"
            "/report monthly"
        )
        return

    try:
        window = REPORT_WINDOWS[period]
        pool = await get_pool()

        async with pool.acquire() as conn:
            summary = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM channels
                     WHERE created_at >= NOW() - $1::interval) AS channels_added,

                    (SELECT COUNT(*) FROM api_configs
                     WHERE created_at >= NOW() - $1::interval) AS api_configs_added,

                    (SELECT COUNT(*) FROM live_tasks
                     WHERE created_at >= NOW() - $1::interval) AS live_tasks_created,

                    (SELECT COUNT(*) FROM reaction_tasks
                     WHERE created_at >= NOW() - $1::interval) AS reaction_tasks_created,

                    (SELECT COUNT(*) FROM activity_logs
                     WHERE created_at >= NOW() - $1::interval) AS actions_logged
                """,
                window,
            )

            live_status = await conn.fetch(
                """
                SELECT status, COUNT(*) AS total
                FROM live_tasks
                GROUP BY status
                ORDER BY status
                """
            )

            reaction_status = await conn.fetch(
                """
                SELECT status, COUNT(*) AS total
                FROM reaction_tasks
                GROUP BY status
                ORDER BY status
                """
            )

        live_lines = [
            f"{row['status']}: {row['total']}"
            for row in live_status
        ] or ["No live tasks"]

        reaction_lines = [
            f"{row['status']}: {row['total']}"
            for row in reaction_status
        ] or ["No reaction tasks"]

        await message.reply_text(
            f"Activity Report — {period}\n\n"
            f"Channels added: {summary['channels_added']}\n"
            f"API configurations added: {summary['api_configs_added']}\n"
            f"Live tasks created: {summary['live_tasks_created']}\n"
            f"Reaction tasks created: {summary['reaction_tasks_created']}\n"
            f"Logged actions: {summary['actions_logged']}\n\n"
            "Current live-task status:\n"
            + "\n".join(live_lines)
            + "\n\nCurrent reaction-task status:\n"
            + "\n".join(reaction_lines)
            + "\n\nNote: Ye database activity report hai. "
            "Actual joins, reactions ya spending ka verified count nahi."
        )

    except Exception:
        logger.exception("Failed to generate activity report")
        await message.reply_text(
            "Report generate nahi ho saki. Server logs check karein."
        )


async def recentactivity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await _authorized(update):
        return

    message = update.effective_message

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT actor_id, action, details, created_at
                FROM activity_logs
                ORDER BY created_at DESC
                LIMIT 20
                """
            )

        if not rows:
            await message.reply_text("Abhi koi activity log nahi hai.")
            return

        lines = ["Recent activity (latest 20):"]

        for row in rows:
            timestamp = row["created_at"].strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"\nTime: {timestamp}"
                f"\nAdmin ID: {row['actor_id']}"
                f"\nAction: {row['action']}"
                f"\nDetails: {row['details']}"
            )

        await message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Failed to load recent activity")
        await message.reply_text(
            "Recent activity load nahi ho saki."
        )


def get_report_handlers():
    return [
        CommandHandler("report", report),
        CommandHandler("recentactivity", recentactivity),
    ]
