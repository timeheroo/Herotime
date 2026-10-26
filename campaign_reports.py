
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import is_admin
from database import get_pool


logger = logging.getLogger(__name__)


async def campaign_report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show saved campaign settings for registered groups."""

    if not update.effective_user or not is_admin(
        update.effective_user.id
    ):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔ You are not authorized to use this command."
            )
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) > 1:
        await message.reply_text(
            "Usage: /campaign_report [GROUP_ID]"
        )
        return

    pool = get_pool()

    if pool is None:
        await message.reply_text(
            "❌ Database is not initialized."
        )
        return

    try:
        async with pool.acquire() as conn:
            if context.args:
                try:
                    group_id = int(context.args[0])
                except ValueError:
                    await message.reply_text(
                        "❌ GROUP_ID must be a number.\n"
                        "Example: /campaign_report 1"
                    )
                    return

                rows = await conn.fetch(
                    """
                    SELECT
                        g.id AS group_id,
                        g.title,
                        g.group_type,
                        g.service_active AS group_is_active,
                        s.target_viewers,
                        s.service_active,
                        s.stream_status,
                        s.last_event_at,
                        s.updated_at
                    FROM groups AS g
                    LEFT JOIN live_campaign_settings AS s
                        ON s.group_id = g.id
                    WHERE g.id = $1
                    """,
                    group_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        g.id AS group_id,
                        g.title,
                        g.group_type,
                        g.service_active AS group_is_active,
                        s.target_viewers,
                        s.service_active,
                        s.stream_status,
                        s.last_event_at,
                        s.updated_at
                    FROM groups AS g
                    LEFT JOIN live_campaign_settings AS s
                        ON s.group_id = g.id
                    ORDER BY g.id ASC
                    """
                )

    except Exception:
        logger.exception("Campaign report query failed")
        await message.reply_text(
            "❌ Report load nahi ho payi. "
            "Database schema aur Railway logs check karein."
        )
        return

    if not rows:
        await message.reply_text(
            "ℹ️ Is GROUP_ID ke liye koi group nahi mila."
            if context.args
            else "ℹ️ Abhi koi group registered nahi hai."
        )
        return

    # Keep Telegram messages within a safe length.
    lines = ["📊 CAMPAIGN SETTINGS REPORT", ""]

    for row in rows:
        target_viewers = row["target_viewers"]
        service_active = row["service_active"]
        stream_status = row["stream_status"]
        last_event_at = row["last_event_at"]

        if target_viewers is None:
            target_viewers = 100
        if service_active is None:
            service_active = False
        if stream_status is None:
            stream_status = "unknown"

        group_status = (
            "ACTIVE" if row["group_is_active"] else "PAUSED"
        )
        service_status = (
            "RUNNING" if service_active else "STOPPED"
        )

        lines.extend(
            [
                f"🆔 Group ID: {row['group_id']}",
                f"📌 Name: {row['title']}",
                f"🏷 Type: {row['group_type']}",
                f"🔧 Group status: {group_status}",
                f"⚙️ Service setting: {service_status}",
                f"🎯 Target quantity: {target_viewers}",
                f"📡 Saved stream status: {stream_status}",
                f"🕒 Last event: {last_event_at or 'Not recorded'}",
                "—" * 20,
                "",
            ]
        )

    # Send multiple messages if the report is too long.
    output = "\n".join(lines)
    chunks = []

    while len(output) > 3500:
        split_at = output.rfind("\n", 0, 3500)
        if split_at <= 0:
            split_at = 3500
        chunks.append(output[:split_at])
        output = output[split_at:].lstrip("\n")

    if output:
        chunks.append(output)

    for chunk in chunks:
        await message.reply_text(chunk)


def register_campaign_report_handlers(
    application: Application,
) -> None:
    """Register campaign report commands."""
    application.add_handler(
        CommandHandler("campaign_report", campaign_report_command)
    )
