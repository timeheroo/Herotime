
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import is_admin
from database import get_pool


async def campaign_report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user or not update.effective_message:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "You are not authorized to use this command."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                g.id AS group_id,
                g.title,
                g.is_active AS group_is_active,
                COALESCE(s.target_viewers, 100)
                    AS target_viewers,
                COALESCE(s.service_active, FALSE)
                    AS service_active,
                COALESCE(s.stream_status, 'unknown')
                    AS stream_status,
                s.last_event_at
            FROM groups AS g
            LEFT JOIN live_campaign_settings AS s
                ON s.group_id = g.id
            WHERE g.group_type = 'target'
            ORDER BY g.id
            LIMIT 30
            """
        )

    if not rows:
        await update.effective_message.reply_text(
            "No target groups have been registered yet."
        )
        return

    lines = ["Campaign settings report:"]

    for row in rows:
        last_event = row["last_event_at"]
        last_event_text = (
            last_event.strftime("%Y-%m-%d %H:%M UTC")
            if last_event
            else "No event received"
        )

        lines.append(
            f"\n{row['title']} (ID: {row['group_id']})\n"
            f"Target: {row['target_viewers']}\n"
            f"Group active: {row['group_is_active']}\n"
            f"Service active: {row['service_active']}\n"
            f"Saved stream status: {row['stream_status']}\n"
            f"Last event: {last_event_text}"
        )

    report = "\n".join(lines)

    # Telegram messages have a length limit.
    for start in range(0, len(report), 3500):
        await update.effective_message.reply_text(
            report[start:start + 3500]
        )


def register_campaign_report_handlers(application) -> None:
    application.add_handler(
        CommandHandler("campaign_report", campaign_report_command)
    )
