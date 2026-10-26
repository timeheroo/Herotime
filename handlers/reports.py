
from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission


PERIODS = {
    "24h": timedelta(hours=24),
    "72h": timedelta(hours=72),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


async def report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show task counts and audit activity for a selected period."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "view_reports"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    period_name = (
        context.args[0].lower()
        if context.args
        else "daily"
    )

    if period_name not in PERIODS:
        await message.reply_text(
            "Usage: /report daily|weekly|monthly|24h|72h"
        )
        return

    interval = PERIODS[period_name]
    pool = await get_pool()

    async with pool.acquire() as conn:
        channel_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM channels
            WHERE created_at >= NOW() - $1::interval
            """,
            interval,
        )

        live_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM live_tasks
            WHERE created_at >= NOW() - $1::interval
            """,
            interval,
        )

        reaction_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM reaction_tasks
            WHERE created_at >= NOW() - $1::interval
            """,
            interval,
        )

        activity_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM activity_logs
            WHERE created_at >= NOW() - $1::interval
            """,
            interval,
        )

        top_actions = await conn.fetch(
            """
            SELECT action, COUNT(*) AS total
            FROM activity_logs
            WHERE created_at >= NOW() - $1::interval
            GROUP BY action
            ORDER BY total DESC
            LIMIT 10
            """,
            interval,
        )

    lines = [
        f"📊 Activity Report — {period_name}",
        "",
        f"New channel records: {channel_count}",
        f"New live task records: {live_count}",
        f"New reaction task records: {reaction_count}",
        f"Recorded admin actions: {activity_count}",
        "",
        "Top recorded actions:",
    ]

    if top_actions:
        for row in top_actions:
            lines.append(f"• {row['action']}: {row['total']}")
    else:
        lines.append("• Is period mein koi activity log nahi mila.")

    lines.extend([
        "",
        "Note: Yeh database records aur audit actions hain, "
        "actual viewers, reactions ya spending nahi."
    ])

    await message.reply_text("\n".join(lines))


async def recent_activity_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show recent audit events."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "view_reports"
    )
    if not allowed:
        await message.reply_text(reason)
        return

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
        await message.reply_text("Abhi koi activity log available nahi hai.")
        return

    lines = ["🧾 Recent Activity"]

    for row in rows:
        timestamp = row["created_at"].strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"\nTime: {timestamp}\n"
            f"Admin ID: {row['actor_id']}\n"
            f"Action: {row['action']}"
        )

    await message.reply_text("\n".join(lines))


def get_report_handlers():
    return [
        CommandHandler("report", report_command),
        CommandHandler("recentactivity", recent_activity_command),
    ]
