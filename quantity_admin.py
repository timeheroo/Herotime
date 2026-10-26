
import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import database

logger = logging.getLogger(__name__)

MIN_QUANTITY = 1
MAX_QUANTITY = 100000


async def init_quantity_schema():
    """Add quantity settings without deleting existing database data."""
    async with database.connection() as conn:
        await conn.execute("""
            ALTER TABLE groups
            ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 0
        """)
        await conn.execute("""
            ALTER TABLE groups
            ADD COLUMN IF NOT EXISTS service_active BOOLEAN NOT NULL DEFAULT TRUE
        """)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and config.is_admin(user.id))


def normalize_reference(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.startswith(("https://", "http://")):
        parsed = urlparse(value)
        path = parsed.path.strip("/")
        if path.startswith("+") or path.startswith("joinchat/"):
            return "https://t.me/" + path
        value = path.split("/")[0] if path else ""
    if value.startswith("t.me/"):
        value = value[5:].split("/")[0]
    if value.startswith("@"):
        value = value[1:]
    return value.strip()


async def find_group(update, context, reference):
    """Resolve a saved group using username, link, or Telegram chat ID."""
    ref = reference.strip()
    normalized = normalize_reference(ref)
    chat_id = None

    # Public username or public t.me link: ask Telegram for the chat ID.
    if normalized and not normalized.startswith("https://"):
        try:
            chat = await context.bot.get_chat("@" + normalized)
            chat_id = chat.id
        except Exception:
            # It may be a saved private invite link or an existing record.
            logger.info("Username lookup failed for %s", normalized)

    async with database.connection() as conn:
        row = None

        if chat_id is not None:
            row = await conn.fetchrow(
                """
                SELECT * FROM groups
                WHERE telegram_chat_id = $1
                ORDER BY id LIMIT 1
                """,
                chat_id,
            )

        if row is None and ref.lstrip("-").isdigit():
            row = await conn.fetchrow(
                "SELECT * FROM groups WHERE telegram_chat_id = $1 ORDER BY id LIMIT 1",
                int(ref),
            )

        if row is None:
            # Match an already-saved invite link or public username.
            candidates = {ref.rstrip("/").lower()}
            if normalized:
                candidates.update({
                    normalized.lower(),
                    ("@" + normalized).lower(),
                    ("https://t.me/" + normalized).lower(),
                    ("http://t.me/" + normalized).lower(),
                    ("t.me/" + normalized).lower(),
                })

            row = await conn.fetchrow(
                """
                SELECT * FROM groups
                WHERE LOWER(COALESCE(invite_url, '')) = ANY($1::text[])
                   OR LOWER(title) = ANY($1::text[])
                ORDER BY id
                LIMIT 1
                """,
                list(candidates),
            )

    return dict(row) if row else None


async def quantity_command(update, context, action):
    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ Sirf admin is command ka use kar sakta hai."
        )
        return

    message = update.effective_message
    args = context.args

    if len(args) != 2:
        await message.reply_text(
            f"Use: /{action} @username NUMBER\n"
            f"Example: /{action} @yourchannel 100\n\n"
            "Saved public link bhi use kar sakte hain."
        )
        return

    reference, raw_amount = args

    try:
        amount = int(raw_amount)
    except ValueError:
        await message.reply_text("❌ Quantity ek number honi chahiye.")
        return

    if not MIN_QUANTITY <= amount <= MAX_QUANTITY:
        await message.reply_text(
            "❌ Quantity 1 se 100000 ke beech honi chahiye."
        )
        return

    group = await find_group(update, context, reference)
    if not group:
        await message.reply_text(
            "❌ Group/channel ka saved record nahi mila.\n"
            "Pehle /add_group se add karein. Private invite link ko "
            "/set_group_invite se saved record par set karein."
        )
        return

    async with database.connection() as conn:
        async with conn.transaction():
            if action == "set_quantity":
                new_quantity = amount
                await conn.execute(
                    "UPDATE groups SET quantity = $1 WHERE id = $2",
                    new_quantity, group["id"],
                )
            elif action == "increase_quantity":
                new_quantity = await conn.fetchval(
                    """
                    UPDATE groups
                    SET quantity = quantity + $1
                    WHERE id = $2 AND quantity + $1 <= 100000
                    RETURNING quantity
                    """,
                    amount, group["id"],
                )
            else:
                new_quantity = await conn.fetchval(
                    """
                    UPDATE groups
                    SET quantity = quantity - $1
                    WHERE id = $2 AND quantity - $1 >= 0
                    RETURNING quantity
                    """,
                    amount, group["id"],
                )

            if new_quantity is None:
                await message.reply_text(
                    "❌ Quantity update nahi hui. Increase se total "
                    "100000 se zyada ya decrease se 0 se kam ho sakta hai."
                )
                return

    await message.reply_text(
        f"✅ Quantity update ho gayi!\n\n"
        f"Group: {group['title']}\n"
        f"Current quantity: {new_quantity}\n"
        f"Service: {'Active' if group.get('service_active', True) else 'Stopped'}"
    )


async def set_quantity(update, context):
    await quantity_command(update, context, "set_quantity")


async def increase_quantity(update, context):
    await quantity_command(update, context, "increase_quantity")


async def decrease_quantity(update, context):
    await quantity_command(update, context, "decrease_quantity")


def register_quantity_handlers(application: Application):
    application.add_handler(
        CommandHandler("set_quantity", set_quantity)
    )
    application.add_handler(
        CommandHandler("increase_quantity", increase_quantity)
    )
    application.add_handler(
        CommandHandler("decrease_quantity", decrease_quantity)
    )
