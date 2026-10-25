"""
groups.py — Admin group/channel management for the existing database.py schema.

Commands:
  /add_group @publicusername source
  /add_group @publicusername target
  /add_group -1001234567890 source
  /groups
  /group_info @publicusername
  /remove_group @publicusername
  /pause_group @publicusername
  /resume_group @publicusername
  /set_group_invite @publicusername https://t.me/your_invite

Notes:
- The bot must be able to resolve/access the chat to add it by username.
- For a private chat, provide its numeric Telegram chat ID; the bot still needs
  enough access for Telegram's get_chat() to resolve it.
- Pause/resume stores an admin-controlled service flag in PostgreSQL. It does
  not itself run or stop a worker; the task/campaign worker must check this flag.
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import database

logger = logging.getLogger(__name__)

VALID_GROUP_TYPES = {"source", "target"}


async def _admin_only(update: Update) -> bool:
    user = update.effective_user
    if user is None or not config.is_admin(user.id):
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Ye command sirf admin use kar sakta hai.")
        return False
    return True


async def init_group_admin_schema() -> None:
    """Add only the new service flag; preserve all existing data."""
    async with database.connection() as conn:
        await conn.execute(
            """
            ALTER TABLE groups
            ADD COLUMN IF NOT EXISTS service_active BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_groups_title_lower
            ON groups (LOWER(title))
            """
        )


async def _resolve_chat(context: ContextTypes.DEFAULT_TYPE, chat_ref: str):
    """Resolve a public @username or numeric chat ID using Telegram."""
    ref = chat_ref.strip()
    if not ref:
        raise ValueError("Channel username ya numeric chat ID dein.")
    if ref.startswith("https://t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]
    if ref.startswith("t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]
    if ref.startswith("@") or ref.lstrip("-").isdigit():
        return await context.bot.get_chat(ref if ref.startswith("@") else int(ref))
    # Treat a plain word as a public username.
    return await context.bot.get_chat("@" + ref)


async def _find_group(conn, group_ref: str):
    ref = group_ref.strip()
    if ref.startswith("https://t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]
    if ref.startswith("t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]

    if ref.lstrip("-").isdigit():
        return await conn.fetchrow(
            "SELECT * FROM groups WHERE telegram_chat_id = $1 LIMIT 1",
            int(ref),
        )

    username = ref[1:] if ref.startswith("@") else ref
    return await conn.fetchrow(
        """
        SELECT * FROM groups
        WHERE LOWER(title) = LOWER($1)
           OR LOWER(COALESCE(invite_url, '')) IN (
                LOWER($2), LOWER($3), LOWER($4)
           )
        ORDER BY id DESC
        LIMIT 1
        """,
        username,
        "@" + username,
        "https://t.me/" + username,
        "t.me/" + username,
    )


async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage:\n/add_group @channelusername source\n"
            "/add_group @channelusername target\n"
            "/add_group -1001234567890 target\n\n"
            "Type sirf source ya target ho sakta hai."
        )
        return

    chat_ref, group_type = context.args[0], context.args[1].lower()
    if group_type not in VALID_GROUP_TYPES:
        await update.effective_message.reply_text("Type `source` ya `target` hona chahiye.")
        return

    try:
        chat = await _resolve_chat(context, chat_ref)
    except Exception as exc:
        logger.info("Unable to resolve Telegram chat %s: %s", chat_ref, exc)
        await update.effective_message.reply_text(
            "❌ Telegram chat resolve nahi hua. Public @username check karein, "
            "ya numeric chat ID dein. Private channel ke liye bot access zaroori ho sakta hai."
        )
        return

    admin_user = update.effective_user
    try:
        async with database.connection() as conn:
            db_user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1",
                admin_user.id,
            )
            if db_user is None:
                db_user = await conn.fetchrow(
                    """
                    INSERT INTO users (telegram_id, username, display_name, role, status)
                    VALUES ($1, $2, $3, 'admin', 'approved')
                    ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        display_name = EXCLUDED.display_name,
                        role = 'admin',
                        status = 'approved'
                    RETURNING id
                    """,
                    admin_user.id,
                    admin_user.username,
                    admin_user.full_name,
                )

            existing = await conn.fetchrow(
                "SELECT id FROM groups WHERE telegram_chat_id = $1",
                chat.id,
            )
            if existing:
                await update.effective_message.reply_text(
                    f"ℹ️ Ye chat pehle se add hai. Database Group ID: {existing['id']}"
                )
                return

            invite_url = None
            if getattr(chat, "username", None):
                invite_url = "https://t.me/" + chat.username

            row = await conn.fetchrow(
                """
                INSERT INTO groups
                    (owner_user_id, telegram_chat_id, title, group_type, invite_url, consent_verified)
                VALUES ($1, $2, $3, $4, $5, FALSE)
                RETURNING id
                """,
                db_user["id"],
                chat.id,
                chat.title or getattr(chat, "username", None) or str(chat.id),
                group_type,
                invite_url,
            )
        await update.effective_message.reply_text(
            f"✅ Chat add ho gaya.\n"
            f"Database Group ID: {row['id']}\n"
            f"Title: {chat.title or 'N/A'}\n"
            f"Telegram Chat ID: {chat.id}\n"
            f"Type: {group_type}\n"
            f"Service: Active"
        )
    except Exception:
        logger.exception("Failed to add group")
        await update.effective_message.reply_text(
            "❌ Group database mein add nahi ho saka. Railway logs check karein."
        )


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return
    try:
        async with database.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, telegram_chat_id, group_type,
                       service_active, invite_url
                FROM groups
                ORDER BY id DESC
                LIMIT 50
                """
            )
        if not rows:
            await update.effective_message.reply_text("Abhi koi group/channel add nahi hai.")
            return
        lines = ["📋 Groups/Channels (latest 50):"]
        for r in rows:
            status = "🟢 Active" if r["service_active"] else "🔴 Paused"
            lines.append(
                f"\nID: {r['id']} | {r['group_type']} | {status}\n"
                f"Name: {r['title']}\nChat ID: {r['telegram_chat_id']}"
            )
        message = "\n".join(lines)
        for start in range(0, len(message), 3800):
            await update.effective_message.reply_text(message[start:start + 3800])
    except Exception:
        logger.exception("Failed to list groups")
        await update.effective_message.reply_text("❌ Groups list nahi ho saki. Railway logs check karein.")


async def group_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /group_info @username_or_chat_id")
        return
    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])
        if not row:
            await update.effective_message.reply_text("Group database mein nahi mila.")
            return
        await update.effective_message.reply_text(
            f"📌 Group information\n"
            f"Database ID: {row['id']}\n"
            f"Title: {row['title']}\n"
            f"Telegram Chat ID: {row['telegram_chat_id']}\n"
            f"Type: {row['group_type']}\n"
            f"Service: {'Active' if row['service_active'] else 'Paused'}\n"
            f"Invite/username: {row['invite_url'] or 'Not set'}\n"
            f"Consent verified: {row['consent_verified']}"
        )
    except Exception:
        logger.exception("Failed to get group info")
        await update.effective_message.reply_text("❌ Group info nahi mil saki.")


async def _set_service(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool) -> None:
    if not await _admin_only(update):
        return
    if not context.args:
        command = "resume_group" if enabled else "pause_group"
        await update.effective_message.reply_text(f"Usage: /{command} @username_or_chat_id")
        return
    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])
            if not row:
                await update.effective_message.reply_text("Group database mein nahi mila.")
                return
            await conn.execute(
                "UPDATE groups SET service_active = $1 WHERE id = $2",
                enabled,
                row["id"],
            )
        state = "ACTIVE 🟢" if enabled else "PAUSED 🔴"
        await update.effective_message.reply_text(
            f"✅ {row['title']} ka service flag {state} kar diya.\n"
            "Note: Actual task/campaign worker ko is flag ko check karna hoga."
        )
    except Exception:
        logger.exception("Failed to change group service state")
        await update.effective_message.reply_text("❌ Service state update nahi hua.")


async def pause_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_service(update, context, False)


async def resume_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_service(update, context, True)


async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /remove_group @username_or_chat_id")
        return
    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])
            if not row:
                await update.effective_message.reply_text("Group database mein nahi mila.")
                return
            # Explicit delete is limited to this group row; linked settings may
            # cascade according to the existing database schema.
            await conn.execute("DELETE FROM groups WHERE id = $1", row["id"])
        await update.effective_message.reply_text(
            f"🗑️ {row['title']} database se remove ho gaya. Telegram channel delete nahi hua."
        )
    except Exception:
        logger.exception("Failed to remove group")
        await update.effective_message.reply_text("❌ Group remove nahi hua. Linked records check karein.")


async def set_group_invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /set_group_invite @username https://t.me/invite_link"
        )
        return
    group_ref, invite_url = context.args[0], context.args[1]
    if not (invite_url.startswith("https://t.me/") or invite_url.startswith("http://t.me/")):
        await update.effective_message.reply_text("Invite URL https://t.me/... format mein dein.")
        return
    try:
        async with database.connection() as conn:
            row = await _find_group(conn, group_ref)
            if not row:
                await update.effective_message.reply_text("Group database mein nahi mila.")
                return
            await conn.execute(
                "UPDATE groups SET invite_url = $1 WHERE id = $2",
                invite_url,
                row["id"],
            )
        await update.effective_message.reply_text(f"✅ Invite URL update ho gaya: {row['title']}")
    except Exception:
        logger.exception("Failed to update group invite")
        await update.effective_message.reply_text("❌ Invite URL update nahi hua.")


def register_group_handlers(application: Application) -> None:
    """Call this from bot.py after the database pool has been initialized."""
    application.add_handler(CommandHandler("add_group", add_group_command))
    application.add_handler(CommandHandler("groups", groups_command))
    application.add_handler(CommandHandler("group_info", group_info_command))
    application.add_handler(CommandHandler("remove_group", remove_group_command))
    application.add_handler(CommandHandler("pause_group", pause_group_command))
    application.add_handler(CommandHandler("resume_group", resume_group_command))
    application.add_handler(CommandHandler("set_group_invite", set_group_invite_command))
