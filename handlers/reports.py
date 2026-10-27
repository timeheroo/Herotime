
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
):
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    allowed, message = await require_permission(
        user_id, "view_reports"
    )
    if not allowed:
        await update.message.reply_text(message)
        return

    period_name = (
        context.args[0].lower()
        if context.args
        else "daily"
    )

    if period_name not in PERIODS:
        await update.message.reply_text(
            "Usage: /report [24h|72h|daily|weekly|monthly]\n\n"
            "Examples:\n"
            "/report daily\n"
            "/report 24h\n"
            "/report 72h\n"
            "/report weekly\n"
            "/report monthly"
        )
        return

    interval = PERIODS[period_name]
    pool = await get_pool()

    async with pool.acquire() as conn:
        channel_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM channels
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        live_task_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM live_tasks
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        reaction_task_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM reaction_tasks
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        account_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM accounts
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        activity_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM activity_logs
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        action_rows = await conn.fetch(
            """
            SELECT action, COUNT(*) AS total
            FROM activity_logs
            WHERE created_at >= NOW() - $1
            GROUP BY action
            ORDER BY total DESC
            LIMIT 10
            """,
            interval,
        )

    lines = [
        f"📊 Activity Report: {period_name}",
        "",
        f"New channel records: {channel_count}",
        f"New account records: {account_count}",
        f"New live task records: {live_task_count}",
        f"New reaction task records: {reaction_task_count}",
        f"Logged activities: {activity_count}",
        "",
        "Top recorded actions:",
    ]

    if action_rows:
        for row in action_rows:
            lines.append(
                f"• {row['action']}: {row['total']}"
            )
    else:
        lines.append("Is period mein koi logged action nahi mila.")

    lines.extend([
        "",
        "Note: Yeh database records aur audit logs ki report hai.",
        "Yeh actual viewers, reactions ya financial spending "
        "ka measurement nahi hai.",
    ])

    await update.message.reply_text("\n".join(lines))


async def recent_activity_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.message:
        return

    allowed, message = await require_permission(
        update.effective_user.id, "view_reports"
    )
    if not allowed:
        await update.message.reply_text(message)
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
        await update.message.reply_text(
            "Abhi activity logs available nahi hain."
        )
        return

    lines = ["🧾 Recent Activity (latest 20):", ""]

    for row in rows:
        lines.append(
            f"Action: {row['action']}\n"
            f"Admin ID: {row['actor_id']}\n"
            f"Time: {row['created_at']}\n"
        )

    await update.message.reply_text("\n".join(lines))


def get_report_handlers():
    return [
        CommandHandler("report", report_command),
        CommandHandler("recentactivity", recent_activity_command),
    ]
