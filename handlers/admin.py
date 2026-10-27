```python
import json
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
)

from config import OWNER_ADMIN_ID
from database import get_pool
from utils.logger import log_action
from utils.permissions import list_admins

logger = logging.getLogger(__name__)

ALLOWED_PERMISSIONS = {
    "manage_channels",
    "manage_live",
    "manage_reactions",
    "view_reports",
    "manage_accounts",
}


async def owner_only(update: Update) -> bool:
    """Allow only the configured owner to manage administrators."""
    user = update.effective_user
    if user is None or user.id != OWNER_ADMIN_ID:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ Ye command sirf Owner Admin use kar sakta hai."
            )
        return False
    return True


async def admins_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await owner_only(update):
        return

    try:
        admins = await list_admins()

        if not admins:
            await update.effective_message.reply_text(
                "Abhi database mein koi admin nahi mila."
            )
            return

        lines = ["👑 **Admin List**", ""]

        for admin in admins:
            role = admin.get("role", "sub_admin")
            username = admin.get("username") or "Not set"
            lines.append(
                f"• ID: `{admin['user_id']}`\n"
                f"  Username: {username}\n"
                f"  Role: {role}"
            )

        await update.effective_message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )

    except Exception:
        logger.exception("Could not list admins")
        await update.effective_message.reply_text(
            "❌ Admin list load nahi hui. Database check karein."
        )


async def add_admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await owner_only(update):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Use:\n/addadmin USER_ID [username]\n\n"
            "Example:\n/addadmin 123456789 myusername"
        )
        return

    try:
        user_id = int(context.args[0])
        if user_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Valid numeric Telegram USER_ID dein."
        )
        return

    if user_id == OWNER_ADMIN_ID:
        await update.effective_message.reply_text(
            "Ye user pehle se Owner Admin hai."
        )
        return

    username = context.args[1].lstrip("@") if len(context.args) > 1 else None
    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT user_id, role FROM admins WHERE user_id = $1",
                user_id,
            )

            if existing:
                await update.effective_message.reply_text(
                    "⚠️ Ye user pehle se admin list mein hai."
                )
                return

            await conn.execute(
                """
                INSERT INTO admins
                    (user_id, username, role, permissions, added_by)
                VALUES ($1, $2, 'sub_admin', $3::jsonb, $4)
                """,
                user_id,
                username,
                json.dumps({}),
                update.effective_user.id,
            )

        await log_action(
            update.effective_user.id,
            "add_admin",
            {"target_user_id": user_id, "username": username},
        )

        await update.effective_message.reply_text(
            f"✅ Sub-admin add ho gaya.\n"
            f"User ID: {user_id}\n"
            f"Username: {username or 'Not set'}\n\n"
            "Default permissions abhi OFF hain.\n"
            "Permission dene ke liye /setpermission use karein."
        )

    except Exception:
        logger.exception("Could not add admin")
        await update.effective_message.reply_text(
            "❌ Admin add nahi hua. Database schema aur logs check karein."
        )


async def set_permission_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await owner_only(update):
        return

    if len(context.args) != 3:
        await update.effective_message.reply_text(
            "Use:\n/setpermission USER_ID PERMISSION on|off\n\n"
            "Example:\n/setpermission 123456789 manage_channels on\n\n"
            "Permissions:\n"
            + "\n".join(sorted(ALLOWED_PERMISSIONS))
        )
        return

    try:
        target_id = int(context.args[0])
        if target_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Valid numeric USER_ID dein."
        )
        return

    permission = context.args[1].lower()
    value = context.args[2].lower()

    if permission not in ALLOWED_PERMISSIONS:
        await update.effective_message.reply_text(
            "❌ Invalid permission.\nAllowed:\n"
            + "\n".join(sorted(ALLOWED_PERMISSIONS))
        )
        return

    if value not in {"on", "off"}:
        await update.effective_message.reply_text(
            "❌ Last argument `on` ya `off` hona chahiye."
        )
        return

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT role, permissions FROM admins WHERE user_id = $1",
                target_id,
            )

            if not row:
                await update.effective_message.reply_text(
                    "❌ Is USER_ID ka admin nahi mila. Pehle /addadmin karein."
                )
                return

            if row["role"] == "owner" or target_id == OWNER_ADMIN_ID:
                await update.effective_message.reply_text(
                    "Owner Admin ki permissions yahan change nahi ki ja sakti."
                )
                return

            permissions = row["permissions"] or {}
            if isinstance(permissions, str):
                permissions = json.loads(permissions)

            if not isinstance(permissions, dict):
                permissions = {}

            permissions[permission] = value == "on"

            await conn.execute(
                """
                UPDATE admins
                SET permissions = $1::jsonb
                WHERE user_id = $2
                """,
                json.dumps(permissions),
                target_id,
            )

        await log_action(
            update.effective_user.id,
            "set_admin_permission",
            {
                "target_user_id": target_id,
                "permission": permission,
                "enabled": value == "on",
            },
        )

        await update.effective_message.reply_text(
            f"✅ Permission update ho gayi.\n"
            f"Admin ID: {target_id}\n"
            f"Permission: {permission}\n"
            f"Status: {value.upper()}"
        )

    except Exception:
        logger.exception("Could not update admin permission")
        await update.effective_message.reply_text(
            "❌ Permission update nahi hui. Railway logs check karein."
        )


async def remove_admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await owner_only(update):
        return

    if len(context.args) != 1:
        await update.effective_message.reply_text(
            "Use:\n/removeadmin USER_ID\n\n"
            "Example:\n/removeadmin 123456789"
        )
        return

    try:
        target_id = int(context.args[0])
        if target_id <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Valid numeric USER_ID dein."
        )
        return

    if target_id == OWNER_ADMIN_ID:
        await update.effective_message.reply_text(
            "❌ Owner Admin ko remove nahi kiya ja sakta."
        )
        return

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT role FROM admins WHERE user_id = $1",
                target_id,
            )

            if not row:
                await update.effective_message.reply_text(
                    "⚠️ Ye admin database mein nahi mila."
                )
                return

            if row["role"] == "owner":
                await update.effective_message.reply_text(
                    "❌ Owner role wala admin remove nahi kiya ja sakta."
                )
                return

            await conn.execute(
                "DELETE FROM admins WHERE user_id = $1",
                target_id,
            )

        await log_action(
            update.effective_user.id,
            "remove_admin",
            {"target_user_id": target_id},
        )

        await update.effective_message.reply_text(
            f"✅ Sub-admin {target_id} remove ho gaya."
        )

    except Exception:
        logger.exception("Could not remove admin")
        await update.effective_message.reply_text(
            "❌ Admin remove nahi hua. Railway logs check karein."
        )


async def adminhelp_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await owner_only(update):
        return

    await update.effective_message.reply_text(
        "👑 OWNER ADMIN COMMANDS\n\n"
        "/admins - Admin list\n"
        "/addadmin USER_ID [username] - Sub-admin add\n"
        "/setpermission USER_ID PERMISSION on|off - Permission change\n"
        "/removeadmin USER_ID - Sub-admin remove\n\n"
        "Available permissions:\n"
        + "\n".join(sorted(ALLOWED_PERMISSIONS))
    )


def get_admin_handlers():
    return [
        CommandHandler("admins", admins_command),
        CommandHandler("addadmin", add_admin_command),
        CommandHandler("setpermission", set_permission_command),
        CommandHandler("removeadmin", remove_admin_command),
        CommandHandler("adminhelp", adminhelp_command),
    ]
```
