"""Admin-only Telegram API account registry.

Requires:
- cryptography package
- API_CREDENTIALS_KEY in Railway Variables (Fernet encryption key)

Commands:
  /add_api <account_name> <api_id> <api_hash>
  /api_accounts
  /remove_api <account_name>

IMPORTANT: register_api_handlers(application) must also be called in bot.py.
This stores API app credentials only; it does not create a Telegram login session.
"""

import logging
import os
import re

from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import connection

logger = logging.getLogger(__name__)

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS api_accounts (
    id BIGSERIAL PRIMARY KEY,
    account_name TEXT NOT NULL UNIQUE,
    api_id BIGINT NOT NULL,
    api_hash_encrypted TEXT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def _fernet() -> Fernet:
    key = os.getenv("API_CREDENTIALS_KEY", "").strip()
    if not key:
        raise RuntimeError("API_CREDENTIALS_KEY missing hai. Railway Variables mein Fernet key add karein.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("API_CREDENTIALS_KEY valid Fernet key nahi hai.") from exc


async def _ensure_table() -> None:
    async with connection() as conn:
        await conn.execute(_TABLE_SQL)


def _is_private(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


async def add_api_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, message = update.effective_user, update.effective_message
    if user is None or message is None:
        return
    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return
    if not _is_private(update):
        await message.reply_text("🔒 Security ke liye /add_api sirf bot ke private chat mein use karein.")
        return
    if len(context.args) != 3:
        await message.reply_text(
            "Format: /add_api <account_name> <api_id> <api_hash>\n"
            "⚠️ Is command mein API Hash chat message mein aayega. Behtar security ke liye "
            "Railway Variables use karein aur command message baad mein delete kar dein."
        )
        return

    name, api_id_raw, api_hash = context.args
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        await message.reply_text("❌ Account name 1–40 characters ka ho: letters, numbers, _ ya -.")
        return
    if not api_id_raw.isdigit() or int(api_id_raw) <= 0:
        await message.reply_text("❌ API ID positive number hona chahiye.")
        return
    if not 20 <= len(api_hash) <= 128:
        await message.reply_text("❌ API Hash ka format/length sahi nahi lag raha.")
        return

    try:
        encrypted_hash = _fernet().encrypt(api_hash.encode("utf-8")).decode("ascii")
        await _ensure_table()
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO api_accounts (account_name, api_id, api_hash_encrypted, created_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (account_name) DO UPDATE SET
                    api_id = EXCLUDED.api_id,
                    api_hash_encrypted = EXCLUDED.api_hash_encrypted,
                    created_by = EXCLUDED.created_by
                """,
                name, int(api_id_raw), encrypted_hash, user.id,
            )
        await message.reply_text(
            f"✅ API account '{name}' encrypted form mein save ho gaya.\n"
            "API Hash list command mein show nahi hoga. Ye credentials apne aap login session nahi banate."
        )
    except RuntimeError as exc:
        await message.reply_text(f"⚙️ Setup required: {exc}")
    except Exception:
        logger.exception("API account save failed; credentials were not logged.")
        await message.reply_text("❌ Save nahi ho saka. Railway logs mein error check karein.")


async def api_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, message = update.effective_user, update.effective_message
    if user is None or message is None:
        return
    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return
    try:
        await _ensure_table()
        async with connection() as conn:
            rows = await conn.fetch(
                "SELECT account_name, api_id, created_at FROM api_accounts ORDER BY account_name"
            )
        if not rows:
            await message.reply_text("Abhi koi API account save nahi hai.")
            return
        lines = ["🔐 Saved API Accounts", ""]
        for row in rows:
            created = row["created_at"].strftime("%Y-%m-%d") if row["created_at"] else "unknown"
            lines.append(f"• {row['account_name']} — API ID: {row['api_id']} — added: {created}")
        await message.reply_text("\n".join(lines))
    except Exception:
        logger.exception("API account list failed.")
        await message.reply_text("❌ List nahi ho saki. Database/setup logs check karein.")


async def remove_api_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, message = update.effective_user, update.effective_message
    if user is None or message is None:
        return
    if not config.is_admin(user.id):
        await message.reply_text("⛔ Admin access required.")
        return
    if len(context.args) != 1:
        await message.reply_text("Format: /remove_api <account_name>")
        return
    name = context.args[0]
    try:
        await _ensure_table()
        async with connection() as conn:
            result = await conn.execute("DELETE FROM api_accounts WHERE account_name = $1", name)
        await message.reply_text(
            f"🗑️ API account '{name}' delete ho gaya." if result.endswith(" 1")
            else f"ℹ️ '{name}' naam ka account nahi mila."
        )
    except Exception:
        logger.exception("API account removal failed.")
        await message.reply_text("❌ Delete nahi ho saka. Database/setup logs check karein.")


def register_api_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("add_api", add_api_command))
    application.add_handler(CommandHandler("api_accounts", api_accounts_command))
    application.add_handler(CommandHandler("remove_api", remove_api_command))
