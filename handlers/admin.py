
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
from utils.validators import validate_telegram_user_id

logger = logging.getLogger(__name__)

VALID_PERMISSIONS = {
    "manage_admins",
    "manage_channels",
    "manage_accounts",
    "manage_live",
    "manage_reactions",
    "view_reports",
}


async def owner_only(update: Update) -> bool:
    """Allow sensitive admin-management commands for the owner only."""
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return False

    if user.id != OWNER_ADMIN_ID:
        await message.reply_text(
            "⛔ Yeh command sirf Owner Admin use kar sakta hai."
        )
        return False

    return True


async def add_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Add a sub-admin using their numeric Telegram user ID."""
    if not await owner_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /addadmin USER_ID\n"
            "Example: /addadmin 123456789"
        )
        return

    try:
        user_id = validate_telegram_user_id(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    if user_id == OWNER_ADMIN_ID:
        await message.reply_text(
            "Owner Admin ko dobara sub-admin add karne ki zaroorat nahi hai."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO admins (user_id, role, permissions, added_by)
            VALUES ($1, 'sub_admin', '{}'::jsonb, $2)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            OWNER_ADMIN_ID,
        )

        admin = await conn.fetchrow(
            "SELECT role FROM admins WHERE user_id = $1",
            user_id,
        )

    if admin is None:
        await message.reply_text("Admin add nahi ho saka.")
        return

    if admin["role"] != "sub_admin":
        await message.reply_text(
            "Yeh ID pehle se Owner role mein hai; koi change nahi kiya."
        )
        return

    await log_action(
        OWNER_ADMIN_ID,
        "sub_admin_added",
        {"target_user_id": user_id},
    )

    await message.reply_text(
        f"✅ Sub-admin ID: {user_id}\n"
        "Default permissions: none\n\n"
        "Access dene ke liye /grant use karein."
    )


async def remove_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Remove a sub-admin. The owner cannot be removed."""
    if not await owner_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /removeadmin USER_ID"
        )
        return

    try:
        user_id = validate_telegram_user_id(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    if user_id == OWNER_ADMIN_ID:
        await message.reply_text(
            "⛔ Owner Admin ko is command se remove nahi kar sakte."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM admins
            WHERE user_id = $1 AND role = 'sub_admin'
            """,
            user_id,
        )

    removed = result.endswith("1")

    if not removed:
        await message.reply_text(
            "Yeh sub-admin ID database mein nahi mili."
        )
        return

    await log_action(
        OWNER_ADMIN_ID,
        "sub_admin_removed",
        {"target_user_id": user_id},
    )

    await message.reply_text(
        f"✅ Sub-admin {user_id} remove kar diya gaya."
    )


async def grant_permission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Grant one supported permission to a sub-admin."""
    if not await owner_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage: /grant USER_ID PERMISSION\n\n"
            "Available permissions:\n"
            + "\n".join(sorted(VALID_PERMISSIONS))
            + "\n\nExample: /grant 123456789 view_reports"
        )
        return

    try:
        user_id = validate_telegram_user_id(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    permission = context.args[1].strip().lower()

    if permission not in VALID_PERMISSIONS:
        await message.reply_text(
            "Invalid permission.\n"
            "Available: " + ", ".join(sorted(VALID_PERMISSIONS))
        )
        return

    if user_id == OWNER_ADMIN_ID:
        await message.reply_text(
            "Owner Admin ke paas pehle se full control hai."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role, permissions FROM admins WHERE user_id = $1",
            user_id,
        )

        if admin is None or admin["role"] != "sub_admin":
            await message.reply_text(
                "Pehle /addadmin USER_ID se sub-admin add karein."
            )
            return

        permissions = admin["permissions"] or {}
        permissions[permission] = True

        await conn.execute(
            """
            UPDATE admins
            SET permissions = $2::jsonb
            WHERE user_id = $1 AND role = 'sub_admin'
            """,
            user_id,
            json.dumps(permissions),
        )

    await log_action(
        OWNER_ADMIN_ID,
        "permission_granted",
        {
            "target_user_id": user_id,
            "permission": permission,
        },
    )

    await message.reply_text(
        f"✅ Permission granted\n"
        f"Admin ID: {user_id}\n"
        f"Permission: {permission}"
    )


async def revoke_permission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Revoke one permission from a sub-admin."""
    if not await owner_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) != 2:
        await message.reply_text(
            "Usage: /revoke USER_ID PERMISSION\n"
            "Example: /revoke 123456789 view_reports"
        )
        return

    try:
        user_id = validate_telegram_user_id(context.args[0])
    except ValueError as exc:
        await message.reply_text(str(exc))
        return

    permission = context.args[1].strip().lower()

    if permission not in VALID_PERMISSIONS:
        await message.reply_text("Invalid permission.")
        return

    if user_id == OWNER_ADMIN_ID:
        await message.reply_text(
            "Owner Admin ki full permission is command se revoke nahi hogi."
        )
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        admin = await conn.fetchrow(
            "SELECT role, permissions FROM admins WHERE user_id = $1",
            user_id,
        )

        if admin is None or admin["role"] != "sub_admin":
            await message.reply_text("Sub-admin nahi mila.")
            return

        permissions = admin["permissions"] or {}
        permissions.pop(permission, None)

        await conn.execute(
            """
            UPDATE admins
            SET permissions = $2::jsonb
            WHERE user_id = $1 AND role = 'sub_admin'
            """,
            user_id,
            json.dumps(permissions),
        )

    await log_action(
        OWNER_ADMIN_ID,
        "permission_revoked",
        {
            "target_user_id": user_id,
            "permission": permission,
        },
    )

    await message.reply_text(
        f"✅ Permission revoke kar di gayi.\n"
        f"Admin ID: {user_id}\n"
        f"Permission: {permission}"
    )


async def list_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """List the owner and registered sub-admins."""
    if not await owner_only(update):
        return

    message = update.effective_message
    if message is None:
        return

    pool = await get_pool()

    async with pool.acquire() as conn:
        admins = await conn.fetch(
            """
            SELECT user_id, role, permissions
            FROM admins
            ORDER BY role, user_id
            """
        )

    if not admins:
        await message.reply_text("Database mein admins nahi mile.")
        return

    lines = ["👥 Admin List"]

    for admin in admins:
        permissions = admin["permissions"] or {}

        if admin["role"] == "owner":
            access = "FULL ACCESS"
        else:
            enabled = sorted(
                key for key, value in permissions.items()
                if value is True and key in VALID_PERMISSIONS
            )
            access = ", ".join(enabled) if enabled else "No permissions"

        lines.append(
            f"\nID: {admin['user_id']}\n"
            f"Role: {admin['role']}\n"
            f"Access: {access}"
        )

    await message.reply_text("\n".join(lines))


def get_admin_handlers():
    """Return owner admin-management command handlers."""
    return [
        CommandHandler("addadmin", add_admin),
        CommandHandler("removeadmin", remove_admin),
        CommandHandler("grant", grant_permission),
        CommandHandler("revoke", revoke_permission),
        CommandHandler("admins", list_admins),
  ]
