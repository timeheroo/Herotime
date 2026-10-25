
"""Admin-only API credential registry.

Commands (bot ke private chat mein):
  /add_api <account_name> <api_id> <api_hash>
  /api_accounts
  /remove_api <account_name>

WARNING: API Hash PostgreSQL mein plain text save hota hai.
Ye credentials apne aap Telegram login session nahi banate.
"""

import logging
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import connection

logger = logging.getLogger(__name__)


async def ensure_api_table():
    """Create the table if it doesn't exist; keep existing records."""
    async with connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_accounts (
                id BIGSERIAL PRIMARY KEY,
                account_name TEXT NOT NULL UNIQUE,
                api_id BIGINT NOT NULL,
                api_hash TEXT,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Compatible with a table previously created by an encrypted version.
        await conn.execute("""
            ALTER TABLE api_accounts
            ADD COLUMN IF NOT EXISTS api_hash TEXT
        """)

        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'api_accounts'
                      AND column_name = 'api_hash_encrypted'
                ) THEN
                    ALTER TABLE api_accounts
                    ALTER COLUMN api_hash_encrypted DROP NOT NULL;
                END IF;
            END $$;
        """)


def is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


async def add_api_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return

    if not is_private_chat(update):
        await message.reply_text(
            "🔒 Security ke liye /add_api sirf bot ke private chat mein use karein."
        )
        return

    if len(context.args) != 3:
        await message.reply_text(
            "Format:\n"
            "/add_api <account_name> <api_id> <api_hash>\n\n"
            "Warning: API Hash database mein plain text save hoga."
        )
        return

    name, api_id_text, api_hash = context.args

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        await message.reply_text(
            "❌ Account name 1–40 characters ka ho. "
            "Letters, numbers, _ aur - use karein."
        )
        return

    if not api_id_text.isdigit() or int(api_id_text) <= 0:
        await message.reply_text("❌ API ID positive number hona chahiye.")
        return

    if not 20 <= len(api_hash) <= 128:
        await message.reply_text(
            "❌ API Hash ki length sahi nahi lag rahi."
        )
        return

    try:
        await ensure_api_table()

        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO api_accounts
                    (account_name, api_id, api_hash, created_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (account_name)
                DO UPDATE SET
                    api_id = EXCLUDED.api_id,
                    api_hash = EXCLUDED.api_hash,
                    created_by = EXCLUDED.created_by
                """,
                name,
                int(api_id_text),
                api_hash,
                user.id,
            )

        await message.reply_text(
            f"✅ API account '{name}' save ho gaya.\n"
            "⚠️ API Hash encrypted nahi hai.\n"
            "Ye credentials apne aap Telegram login session nahi banate."
        )

    except Exception:
        logger.exception("API account save failed.")
        await message.reply_text(
            "❌ Save nahi ho saka. Railway Deploy Logs check karein."
        )


async def api_accounts_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return

    try:
        await ensure_api_table()

        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT account_name, api_id, created_at
                FROM api_accounts
                ORDER BY account_name
                """
            )

        if not rows:
            await message.reply_text(
                "Abhi koi API account save nahi hai."
            )
            return

        lines = ["🔐 Saved API Accounts", ""]

        for row in rows:
            created_at = row["created_at"]
            date_text = (
                created_at.strftime("%Y-%m-%d")
                if created_at else "unknown"
            )

            lines.append(
                f"• {row['account_name']} — "
                f"API ID: {row['api_id']} — added: {date_text}"
            )

        await message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("API account list failed.")
        await message.reply_text(
            "❌ List nahi ho saki. Railway Deploy Logs check karein."
        )


async def remove_api_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Format: /remove_api <account_name>"
        )
        return

    name = context.args[0]

    try:
        await ensure_api_table()

        async with connection() as conn:
            result = await conn.execute(
                "DELETE FROM api_accounts WHERE account_name = $1",
                name,
            )

        if result.endswith(" 1"):
            await message.reply_text(
                f"🗑️ API account '{name}' delete ho gaya."
            )
        else:
            await message.reply_text(
                f"ℹ️ '{name}' naam ka account nahi mila."
            )

    except Exception:
        logger.exception("API account removal failed.")
        await message.reply_text(
            "❌ Delete nahi ho saka. Railway Deploy Logs check karein."
        )


def register_api_handlers(application: Application):
    application.add_handler(
        CommandHandler("add_api", add_api_command)
    )
    application.add_handler(
        CommandHandler("api_accounts", api_accounts_command)
    )
    application.add_handler(
        CommandHandler("remove_api", remove_api_command)
    )
