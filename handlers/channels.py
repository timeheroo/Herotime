
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action


async def add_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            "Usage: /addchannel @username\n"
            "Example: /addchannel @mychannel"
        )
        return

    username = context.args[0].strip().lstrip("@")
    if not username or not username.replace("_", "").isalnum():
        await message.reply_text("Valid public channel username dein.")
        return

    # Verify that Telegram can resolve this public channel.
    try:
        chat = await context.bot.get_chat(f"@{username}")
    except Exception:
        await message.reply_text(
            "Channel nahi mila. Username check karein aur ensure karein "
            "ki channel public hai."
        )
        return

    if chat.type != "channel":
        await message.reply_text(
            "Yeh Telegram channel nahi lagta. Channel ka public username dein."
        )
        return

    channel_username = chat.username or username
    channel_link = (
        f"https://t.me/{chat.username}"
        if chat.username
        else None
    )

    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT id, is_active
                FROM channels
                WHERE telegram_id = $1
                   OR LOWER(username) = LOWER($2)
                ORDER BY id
                LIMIT 1
                """,
                chat.id,
                channel_username,
            )

            if existing:
                channel_id = existing["id"]
                await conn.execute(
                    """
                    UPDATE channels
                    SET telegram_id = $1,
                        username = $2,
                        title = $3,
                        channel_link = $4,
                        updated_at = NOW()
                    WHERE id = $5
                    """,
                    chat.id,
                    channel_username,
                    chat.title,
                    channel_link,
                    channel_id,
                )
                status = (
                    "active" if existing["is_active"] else "inactive"
                )
                action = "channel_record_updated"
            else:
                channel_id = await conn.fetchval(
                    """
                    INSERT INTO channels (
                        telegram_id, username, title,
                        channel_link, created_by, is_active
                    )
                    VALUES ($1, $2, $3, $4, $5, TRUE)
                    RETURNING id
                    """,
                    chat.id,
                    channel_username,
                    chat.title,
                    channel_link,
                    user.id,
                )
                status = "active"
                action = "channel_record_added"

    await log_action(
        user.id,
        action,
        {
            "channel_id": channel_id,
            "telegram_id": chat.id,
            "username": channel_username,
        },
    )

    await message.reply_text(
        "✅ Channel record ready\n\n"
        f"Record ID: {channel_id}\n"
        f"Title: {chat.title or 'Not available'}\n"
        f"Username: @{channel_username}\n"
        f"Status: {status}\n\n"
        "Note: Record add hone ka matlab yeh nahi ki bot ko "
        "channel mein admin permissions mil gayi hain."
    )


async def list_channels(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            SELECT id, telegram_id, username, title,
                   is_active, created_at
            FROM channels
            ORDER BY id DESC
            LIMIT 50
            """
        )

    if not channels:
        await message.reply_text("Abhi koi channel record nahi hai.")
        return

    lines = ["📢 Channel Records (latest 50)"]

    for channel in channels:
        status = "🟢 Active" if channel["is_active"] else "🔴 Inactive"
        username = (
            f"@{channel['username']}"
            if channel["username"]
            else "Not available"
        )
        lines.append(
            f"\nRecord ID: {channel['id']}\n"
            f"Title: {channel['title'] or 'Not available'}\n"
            f"Username: {username}\n"
            f"Telegram ID: {channel['telegram_id'] or 'Not verified'}\n"
            f"Status: {status}"
        )

    await message.reply_text("\n".join(lines))


async def set_channel_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    active: bool,
) -> None:
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
        command = "activatechannel" if active else "deactivatechannel"
        await message.reply_text(f"Usage: /{command} CHANNEL_RECORD_ID")
        return

    channel_id = int(context.args[0])
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE channels
            SET is_active = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, username, title, is_active
            """,
            active,
            channel_id,
        )

    if row is None:
        await message.reply_text(
            "Channel record nahi mila. /channels se Record ID check karein."
        )
        return

    action = "channel_activated" if active else "channel_deactivated"
    await log_action(
        user.id,
        action,
        {"channel_id": channel_id},
    )

    status = "🟢 Active" if active else "🔴 Inactive"
    await message.reply_text(
        f"✅ Channel record update ho gaya.\n"
        f"Record ID: {row['id']}\n"
        f"Title: {row['title'] or 'Not available'}\n"
        f"Status: {status}\n\n"
        "Note: Yeh database status hai; isse Telegram permissions "
        "automatically change nahi hoti."
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
    return [
        CommandHandler("addchannel", add_channel),
        CommandHandler("channels", list_channels),
        CommandHandler("activatechannel", activate_channel),
        CommandHandler("deactivatechannel", deactivate_channel),
    ]
