
"""
groups.py — Admin group/channel management.
Existing database.py schema ko use karta hai.
Existing group records ko delete ya reset nahi karta.
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
    message = update.effective_message

    if user is None or not config.is_admin(user.id):
        if message:
            await message.reply_text("⛔ Ye command sirf authorized admin use kar sakta hai.")
        return False

    return True


async def init_group_admin_schema() -> None:
    """Add service flag without deleting existing group data."""
    async with database.connection() as conn:
        await conn.execute("""
            ALTER TABLE groups
            ADD COLUMN IF NOT EXISTS service_active
            BOOLEAN NOT NULL DEFAULT TRUE
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_title_lower
            ON groups (LOWER(title))
        """)


async def _resolve_chat(context, chat_ref: str):
    ref = chat_ref.strip()

    if ref.startswith("https://t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]
    elif ref.startswith("t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]

    if ref.startswith("@"):
        return await context.bot.get_chat(ref)

    if ref.lstrip("-").isdigit():
        return await context.bot.get_chat(int(ref))

    return await context.bot.get_chat("@" + ref)


async def _find_group(conn, group_ref: str):
    ref = group_ref.strip()

    if ref.startswith("https://t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]
    elif ref.startswith("t.me/"):
        ref = "@" + ref.rstrip("/").split("/")[-1]

    # Internal database group ID: #12 or id:12
    db_ref = ref.removeprefix("#").removeprefix("id:")

    if db_ref.isdigit():
        row = await conn.fetchrow(
            "SELECT * FROM groups WHERE id = $1",
            int(db_ref),
        )
        if row:
            return row

    # Telegram chat ID
    if ref.lstrip("-").isdigit():
        return await conn.fetchrow(
            "SELECT * FROM groups WHERE telegram_chat_id = $1",
            int(ref),
        )

    username = ref[1:] if ref.startswith("@") else ref

    return await conn.fetchrow(
        """
        SELECT *
        FROM groups
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


async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage:\n"
            "/add_group @username source\n"
            "/add_group @username target\n"
            "/add_group -1001234567890 source"
        )
        return

    chat_ref, group_type = context.args
    group_type = group_type.lower()

    if group_type not in VALID_GROUP_TYPES:
        await message.reply_text("Type sirf source ya target ho sakta hai.")
        return

    try:
        chat = await _resolve_chat(context, chat_ref)
    except Exception:
        logger.exception("Unable to resolve Telegram chat")
        await message.reply_text(
            "❌ Chat resolve nahi hua. Username/chat ID check karein "
            "aur bot ka access verify karein."
        )
        return

    admin = update.effective_user

    try:
        async with database.connection() as conn:
            async with conn.transaction():
                db_user = await conn.fetchrow(
                    "SELECT id FROM users WHERE telegram_id = $1",
                    admin.id,
                )

                if db_user is None:
                    db_user = await conn.fetchrow(
                        """
                        INSERT INTO users
                            (telegram_id, username, display_name, role, status)
                        VALUES ($1, $2, $3, 'admin', 'approved')
                        ON CONFLICT (telegram_id) DO UPDATE
                        SET username = EXCLUDED.username,
                            display_name = EXCLUDED.display_name
                        RETURNING id
                        """,
                        admin.id,
                        admin.username,
                        admin.full_name,
                    )

                existing = await conn.fetchrow(
                    "SELECT id FROM groups WHERE telegram_chat_id = $1",
                    chat.id,
                )

                if existing:
                    await message.reply_text(
                        f"ℹ️ Ye chat pehle se saved hai.\n"
                        f"Database Group ID: {existing['id']}"
                    )
                    return

                invite_url = (
                    f"https://t.me/{chat.username}"
                    if getattr(chat, "username", None)
                    else None
                )

                row = await conn.fetchrow(
                    """
                    INSERT INTO groups
                        (owner_user_id, telegram_chat_id, title,
                         group_type, invite_url, consent_verified)
                    VALUES ($1, $2, $3, $4, $5, FALSE)
                    RETURNING id
                    """,
                    db_user["id"],
                    chat.id,
                    chat.title or chat.username or str(chat.id),
                    group_type,
                    invite_url,
                )

        await message.reply_text(
            f"✅ Group/channel save ho gaya.\n"
            f"Database ID: {row['id']}\n"
            f"Name: {chat.title or chat.username or 'Unknown'}\n"
            f"Telegram ID: {chat.id}\n"
            f"Type: {group_type}\n"
            f"Service: Active"
        )

    except Exception:
        logger.exception("Failed to add group")
        await message.reply_text(
            "❌ Database mein save nahi hua. Railway logs check karein."
        )


async def _list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE, all_rows=False):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    try:
        async with database.connection() as conn:
            query = """
                SELECT id, title, telegram_chat_id, group_type,
                       service_active, invite_url
                FROM groups
                ORDER BY id DESC
            """
            if not all_rows:
                query += " LIMIT 50"

            rows = await conn.fetch(query)

        if not rows:
            await message.reply_text("Abhi koi group/channel saved nahi hai.")
            return

        chunks = []
        current = []

        for row in rows:
            block = (
                f"ID: {row['id']}\n"
                f"Name: {row['title']}\n"
                f"Telegram ID: {row['telegram_chat_id']}\n"
                f"Type: {row['group_type']}\n"
                f"Service: {'Active 🟢' if row['service_active'] else 'Paused 🔴'}\n"
                f"Invite: {row['invite_url'] or 'Not set'}\n"
            )

            if len("\n\n".join(current + [block])) > 3500 and current:
                chunks.append("\n\n".join(current))
                current = []

            current.append(block)

        if current:
            chunks.append("\n\n".join(current))

        for chunk in chunks:
            await message.reply_text(chunk)

    except Exception:
        logger.exception("Failed to list groups")
        await message.reply_text("❌ List nahi mil saki. Railway logs check karein.")


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _list_groups(update, context, all_rows=False)


async def all_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _list_groups(update, context, all_rows=True)


async def group_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if not context.args:
        await message.reply_text(
            "Usage: /group_info ID\n"
            "Example: /group_info 1"
        )
        return

    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])

        if not row:
            await message.reply_text("Group database mein nahi mila.")
            return

        await message.reply_text(
            f"📌 Group information\n"
            f"Database ID: {row['id']}\n"
            f"Name: {row['title']}\n"
            f"Telegram ID: {row['telegram_chat_id']}\n"
            f"Type: {row['group_type']}\n"
            f"Service: {'Active' if row['service_active'] else 'Paused'}\n"
            f"Invite: {row['invite_url'] or 'Not set'}\n"
            f"Consent verified: {row['consent_verified']}"
        )

    except Exception:
        logger.exception("Failed to get group info")
        await message.reply_text("❌ Group info load nahi hui.")


async def search_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if not context.args:
        await message.reply_text("Usage: /search_group name")
        return

    term = " ".join(context.args).strip()

    try:
        async with database.connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, telegram_chat_id, group_type, service_active
                FROM groups
                WHERE title ILIKE $1
                   OR CAST(id AS TEXT) = $2
                   OR CAST(telegram_chat_id AS TEXT) = $2
                ORDER BY id DESC
                LIMIT 30
                """,
                f"%{term}%",
                term,
            )

        if not rows:
            await message.reply_text("Koi matching group/channel nahi mila.")
            return

        lines = ["🔎 Search results:"]
        for row in rows:
            state = "Active" if row["service_active"] else "Paused"
            lines.append(
                f"\nID: {row['id']} | {row['group_type']} | {state}\n"
                f"{row['title']}\n"
                f"Telegram ID: {row['telegram_chat_id']}"
            )

        await message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Group search failed")
        await message.reply_text("❌ Search fail hua.")


async def _set_service(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if not context.args:
        await message.reply_text(
            "Usage: /pause_group DATABASE_GROUP_ID\n"
            "ya /resume_group DATABASE_GROUP_ID"
        )
        return

    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])

            if not row:
                await message.reply_text("Group database mein nahi mila.")
                return

            await conn.execute(
                "UPDATE groups SET service_active = $1 WHERE id = $2",
                enabled,
                row["id"],
            )

        state = "ACTIVE 🟢" if enabled else "PAUSED 🔴"
        await message.reply_text(
            f"✅ {row['title']} ka service flag {state} kar diya.\n"
            "Note: Worker ko bhi service_active check karna hoga."
        )

    except Exception:
        logger.exception("Failed to change service state")
        await message.reply_text("❌ Service state update nahi hua.")


async def pause_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_service(update, context, False)


async def resume_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_service(update, context, True)


async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if not context.args:
        await message.reply_text("Usage: /remove_group DATABASE_GROUP_ID")
        return

    try:
        async with database.connection() as conn:
            row = await _find_group(conn, context.args[0])

            if not row:
                await message.reply_text("Group database mein nahi mila.")
                return

            linked = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tasks WHERE target_group_id = $1)",
                row["id"],
            )

            if linked:
                await message.reply_text(
                    "⚠️ Is group se tasks linked hain. Data safety ke liye "
                    "ise delete nahi kiya. Pehle linked tasks review karein."
                )
                return

            await conn.execute("DELETE FROM groups WHERE id = $1", row["id"])

        await message.reply_text(
            f"🗑️ {row['title']} database se remove ho gaya. "
            "Telegram channel delete nahi hua."
        )

    except Exception:
        logger.exception("Failed to remove group")
        await message.reply_text("❌ Group remove nahi hua.")


async def set_group_invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) < 2:
        await message.reply_text(
            "Usage: /set_group_invite DATABASE_GROUP_ID https://t.me/invite"
        )
        return

    group_ref = context.args[0]
    invite_url = context.args[1].strip()

    if not invite_url.startswith("https://t.me/"):
        await message.reply_text("Invite URL https://t.me/... format mein dein.")
        return

    try:
        async with database.connection() as conn:
            row = await _find_group(conn, group_ref)

            if not row:
                await message.reply_text("Group database mein nahi mila.")
                return

            await conn.execute(
                "UPDATE groups SET invite_url = $1 WHERE id = $2",
                invite_url,
                row["id"],
            )

        await message.reply_text(f"✅ Invite link update ho gaya: {row['title']}")

    except Exception:
        logger.exception("Failed to update invite")
        await message.reply_text("❌ Invite link update nahi hua.")


def register_group_handlers(application: Application) -> None:
    """Register all group/channel administration commands."""
    handlers = [
        ("add_group", add_group_command),
        ("groups", groups_command),
        ("list_groups", groups_command),
        ("all_channels", all_channels_command),
        ("group_info", group_info_command),
        ("search_group", search_group_command),
        ("remove_group", remove_group_command),
        ("pause_group", pause_group_command),
        ("resume_group", resume_group_command),
        ("set_group_invite", set_group_invite_command),
        ("update_invite", set_group_invite_command),
    ]

    for command, callback in handlers:
        application.add_handler(CommandHandler(command, callback))
