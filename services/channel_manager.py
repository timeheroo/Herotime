
from database import get_pool


async def list_channels():
    """Return all registered channels."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, telegram_id, username, title, channel_link,
                   is_active, created_at
            FROM channels
            ORDER BY id DESC
            """
        )

    return [dict(row) for row in rows]


async def get_channel(channel_id: int):
    """Return one channel by its database ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, telegram_id, username, title, channel_link,
                   is_active, created_at
            FROM channels
            WHERE id = $1
            """,
            channel_id,
        )

    return dict(row) if row else None


async def set_channel_status(channel_id: int, is_active: bool) -> bool:
    """Activate or deactivate a registered channel."""
    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE channels
            SET is_active = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            is_active,
            channel_id,
        )

    return result == "UPDATE 1"
