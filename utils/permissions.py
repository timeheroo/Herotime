
from config import OWNER_ADMIN_ID
from database import get_pool


async def is_owner(user_id: int) -> bool:
    """Check whether the user is the configured owner."""
    return user_id == OWNER_ADMIN_ID


async def get_admin(user_id: int):
    """Return an admin record, or None if access is not granted."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT user_id, role, permissions
            FROM admins
            WHERE user_id = $1
            """,
            user_id,
        )


async def has_permission(
    user_id: int,
    permission: str,
) -> bool:
    """Check owner or a specific permission granted to a sub-admin."""
    if await is_owner(user_id):
        return True

    admin = await get_admin(user_id)

    if admin is None:
        return False

    if admin["role"] != "sub_admin":
        return False

    permissions = admin["permissions"] or {}

    if permissions.get("all") is True:
        return True

    return permissions.get(permission) is True


async def require_permission(
    user_id: int,
    permission: str,
) -> tuple[bool, str]:
    """Return an access decision and a readable explanation."""
    if await has_permission(user_id, permission):
        return True, "Access granted."

    return False, "Access denied. Owner Admin se permission lein."
