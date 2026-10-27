
import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from database import get_pool
from utils.permissions import require_permission
from utils.logger import log_action

logger = logging.getLogger(__name__)


def normalize_channel_input(value: str) -> str:
    """Accept @username, username, or a public t.me URL."""
    value = value.strip()

    if value.startswith("@"):
        value = value[1:]

    elif "://" in value:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()

        if host not in {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}:
            raise ValueError(
                "Telegram link use karein, jaise https://t.me/example"
            )

        parts = [part for part in parsed.path.split("/") if part]

        if not parts:
            raise ValueError("Telegram link mein username nahi mila.")

        # Private invite links cannot be resolved like public usernames.
        if parts[0].startswith("+") or parts[0] == "joinchat":
            raise ValueError(
                "Private invite link se channel automatically resolve nahi "
                "ho sakta. Bot ko channel/group mein add karke public "
                "username ya supported chat reference use karein."
            )

        value = parts[0]

    if not value or not value.replace("_", "").isalnum():
        raise ValueError("Valid public Telegram username enter karein.")

    return value


async def resolve_chat(context: ContextTypes.DEFAULT_TYPE, value: str):
    username = normalize_channel_input(value)
    return await context.bot.get_chat(f"@{username}")


async def addchannel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    allowed, reason = await require_permission(
        user.id,
        "manage_channels",
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage:\n"
            "/addchannel @username\n"
            "or\n"
            "/addchannel https://t.me/username"
        )
        return

    try:
        chat = await resolve_chat(context, context.args[0])

        if chat.type not in ("channel", "group", "supergroup"):
            await message.reply_text(
                "Yeh Telegram channel ya group nahi lagta."
            )
            return

        username = chat.username
        link = (
            f"https://t.me/{username}"
            if username
            else None
        )

        pool = await get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO channels
                    (telegram_id, username, title, channel_link,
                     is_active, created_by, updated_at)
                VALUES ($1, $2, $3, $4, TRUE, $5, NOW())
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    title = EXCLUDED.title,
                    channel_link = EXCLUDED.channel_link,
                    is_active = TRUE,
                    updated_at = NOW()
                RETURNING id, title, username
                """,
                chat.id,
                username,
                chat.title or "",
                link,
                user.id,
            )

        await log_action(
            user.id,
            "channel_added_or_updated",
            {
                "channel_id": row["id"],
                "telegram_id": chat.id,
                "username": username,
            },
        )

        identifier = f"@{username}" if username else str(chat.id)

        await message.reply_text(
            "Channel/group saved successfully.\n"
            f"Database ID: {row['id']}\n"
            f"Name: {row['title']}\n"
            f"Username/reference: {identifier}\n"
            "Status: Active"
        )

    except ValueError as exc:
        await message.reply_text(str(exc))
    except Exception:
        logger.exception("Failed to add Telegram channel/group")
        await message.reply_text(
            "Channel/group resolve nahi hua. Check karein ki username "
            "sahi hai aur bot ko required access mila hua hai."
        )


async def channels(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    allowed, reason = await require_permission(
        user.id,
        "manage_channels",
    )
    if not allowed:
        await message.reply_text(reason)
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, username, title,
                   channel_link, is_active
            FROM channels
            ORDER BY id DESC
            """
        )

    if not rows:
        await message.reply_text("Abhi koi channel/group saved nahi hai.")
        return

    lines = ["Registered channels/groups:"]

    for row in rows:
        status = "ACTIVE" if row["is_active"] else "INACTIVE"
        identifier = (
            f"@{row['username']}"
            if row["username"]
            else str(row["telegram_id"])
        )
        lines.append(
            f"\nID: {row['id']}"
            f"\nName: {row['title']}"
            f"\nUsername/reference: {identifier}"
            f"\nStatus: {status}"
        )

    await message.reply_text("\n".join(lines))


async def _set_channel_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    active: bool,
) -> None:
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    allowed, reason = await require_permission(
        user.id,
        "manage_channels",
    )
    if not allowed:
        await message.reply_text(reason)
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage:\n"
            "/activatechannel @username\n"
            "/deactivatechannel @username"
        )
        return

    try:
        username = normalize_channel_input(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE channels
            SET is_active = $1, updated_at = NOW()
            WHERE LOWER(username) = LOWER($2)
            RETURNING id, title, is_active
            """,
            active,
            username,
        )

    if row is None:
        await message.reply_text(
            "Channel/group database mein nahi mila. Pehle /addchannel karein."
        )
        return

    await log_action(
        user.id,
        "channel_activated" if active else "channel_deactivated",
        {"channel_id": row["id"], "username": username},
    )

    status = "ACTIVE" if active else "INACTIVE"
    await message.reply_text(
        f"{row['title']} ka status: {status}"
    )


async def activatechannel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_channel_status(update, context, True)


async def deactivatechannel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await _set_channel_status(update, context, False)


def get_channel_handlers():
    return [
        CommandHandler("addchannel", addchannel),
        CommandHandler("channels", channels),
        CommandHandler("activatechannel", activatechannel),
        CommandHandler("deactivatechannel", deactivatechannel),
    ]
