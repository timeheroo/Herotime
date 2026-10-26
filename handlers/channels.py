
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from database import get_pool
from utils.permissions import require_permission
from utils.validators import validate_channel_username
from utils.logger import log_action


async def add_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Register a public Telegram channel by username."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_channels"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /addchannel @channelname\n"
            "Example: /addchannel @mychannel"
        )
        return

    try:
        username = validate_channel_username(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO channels (
                username, channel_link, created_by, is_active
            )
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (telegram_id) DO NOTHING
            RETURNING id
            """,
            username,
            f"https://t.me/{username.lstrip('@')}",
            user.id,
        )

        if row is None:
            existing = await conn.fetchrow(
                "SELECT id FROM channels WHERE username = $1",
                username,
            )

            if existing:
                await message.reply_text(
                    f"Channel {username} pehle se registered hai."
                )
                return

            await message.reply_text(
                "Channel save nahi ho saka. Dobara try karein."
            )
            return

        channel_id = row["id"]

    await log_action(
        user.id,
        "channel_added",
        {"channel_id": channel_id, "username": username},
    )

    await message.reply_text(
        f"✅ Channel registered\n"
        f"Database ID: {channel_id}\n"
        f"Username: {username}\n\n"
        "Note: Registration se channel access verify nahi hota. "
        "Telegram access check alag se karna hoga."
    )


async def list_channels(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """List registered channels."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_channels"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        channels = await conn.fetch(
            """
            SELECT id, username, channel_link, is_active
            FROM channels
            ORDER BY id DESC
            LIMIT 50
            """
        )

    if not channels:
        await message.reply_text("Abhi koi channel registered nahi hai.")
        return

    lines = ["📋 Registered Channels"]

    for channel in channels:
        status = "Active" if channel["is_active"] else "Inactive"
        username = channel["username"] or "(username unavailable)"
        link = channel["channel_link"] or "(link unavailable)"

        lines.append(
            f"\nID: {channel['id']}\n"
            f"Channel: {username}\n"
            f"Link: {link}\n"
            f"Status: {status}"
        )

    await message.reply_text("\n".join(lines))


async def set_channel_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    active: bool,
) -> None:
    """Activate or deactivate a registered channel."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    allowed, reason = await require_permission(
        user.id, "manage_channels"
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        command = "/activatechannel" if active else "/deactivatechannel"
        await message.reply_text(f"Usage: {command} CHANNEL_ID")
        return

    channel_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE channels
            SET is_active = $2, updated_at = NOW()
            WHERE id = $1
            """,
            channel_id,
            active,
        )

    if result.endswith("0"):
        await message.reply_text("Channel ID nahi mila.")
        return

    action = "channel_activated" if active else "channel_deactivated"

    await log_action(
        user.id,
        action,
        {"channel_id": channel_id},
    )

    status = "activated" if active else "deactivated"
    await message.reply_text(
        f"✅ Channel ID {channel_id} {status}."
    )


async def activate_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_channel_status(update, context, True)


async def deactivate_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await set_channel_status(update, context, False)


def get_channel_handlers():
    """Return channel-management command handlers."""
    return [
        CommandHandler("addchannel", add_channel),
        CommandHandler("channels", list_channels),
        CommandHandler("activatechannel", activate_channel),
        CommandHandler("deactivatechannel", deactivate_channel),
    ]
