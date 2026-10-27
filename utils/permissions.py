
import json
import logging

from database import get_pool

logger = logging.getLogger(__name__)


async def get_admin(user_id: int):
    """Return the admin record, or None if the user is not an admin."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id, username, role, permissions, added_by
            FROM admins
            WHERE user_id = $1
            """,
            user_id,
        )

    return dict(row) if row else None


async def has_permission(user_id: int, permission: str) -> bool:
    """Check whether an admin has a particular permission."""
    admin = await get_admin(user_id)

    if not admin:
        return False

    if admin["role"] == "owner":
        return True

    permissions = admin.get("permissions") or {}

    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except json.JSONDecodeError:
            logger.warning("Invalid permissions JSON for admin %s", user_id)
            return False

    if not isinstance(permissions, dict):
        return False

    return (
        permissions.get("all") is True
        or permissions.get(permission) is True
    )


async def require_permission(user_id: int, permission: str) -> bool:
    """Permission-check helper used by command handlers."""
    return await has_permission(user_id, permission)


async def is_owner(user_id: int) -> bool:
    """Check whether a user has the owner role."""
    admin = await get_admin(user_id)
    return bool(admin and admin["role"] == "owner")


async def list_admins():
    """Return all registered admins."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, username, role, permissions, added_by, created_at
            FROM admins
            ORDER BY created_at ASC
            """
        )

    return [dict(row) for row in rows]
