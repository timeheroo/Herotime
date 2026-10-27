```python
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import get_pool
from utils.permissions import has_permission
from utils.logger import log_action
from utils.validators import normalize_public_channel

logger = logging.getLogger(__name__)


async def resolve_chat(context, username):
    return await context.bot.get_chat(f"@{username}")


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_channels"):
        await message.reply_text("❌ Aapko channels manage karne ki permission nahi hai.")
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Use:\n/addchannel @channelusername\n\n"
            "Example:\n/addchannel @mypublicchannel"
        )
        return

    try:
        username = normalize_public_channel(context.args[0])
        chat = await resolve_chat(context, username)

        if chat.type not in ("channel", "supergroup", "group"):
            await message.reply_text("❌ Yeh Telegram channel ya group nahi hai.")
            return

        pool = await get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO channels
                    (telegram_id, title, username, is_active)
                VALUES ($1, $2, $3, TRUE)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    username = EXCLUDED.username,
                    is_active = TRUE
                RETURNING id, title, username
                """,
                chat.id,
                chat.title or username,
                chat.username,
            )

        await log_action(
            user.id,
            "add_channel",
            {"channel_id": row["id"], "username": row["username"]},
        )

        await message.reply_text(
            "✅ Channel/group add ho gaya!\n"
            f"ID: {row['id']}\n"
            f"Name: {row['title']}\n"
            f"Username: @{row['username'] or 'private'}"
        )

    except ValueError as exc:
        await message.reply_text(f"❌ {exc}")
    except Exception:
        logger.exception("Failed to add channel")
        await message.reply_text(
            "❌ Channel add nahi hua. Username, bot access aur database check karein."
        )


async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not await has_permission(user.id, "manage_channels"):
        await message.reply_text("❌ Aapko channels dekhne ki permission nahi hai.")
        return

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, username, telegram_id, is_active
                FROM channels
                ORDER BY id
                """
            )

        if not rows:
            await message.reply_text("Abhi koi channel/group add nahi hai.")
            return

        lines = ["📋 CHANNELS / GROUPS", ""]

        for row in rows:
            status = "🟢 Ac
```
