
from database import get_pool


async def create_live_task(
    channel_id: int,
    target_quantity: int,
    created_by: int,
):
    """Create a live-task configuration for a registered channel."""
    if target_quantity < 0:
        raise ValueError("Target quantity cannot be negative.")

    pool = get_pool()

    async with pool.acquire() as conn:
        channel = await conn.fetchrow(
            "SELECT id FROM channels WHERE id = $1",
            channel_id,
        )

        if not channel:
            raise ValueError("Channel not found.")

        row = await conn.fetchrow(
            """
            INSERT INTO live_tasks
                (channel_id, target_quantity, status, created_by)
            VALUES ($1, $2, 'stopped', $3)
            RETURNING id, channel_id, target_quantity, status, created_at
            """,
            channel_id,
            target_quantity,
            created_by,
        )

    return dict(row)


async def list_live_tasks():
    """List live-task configurations with channel details."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                lt.id,
                lt.channel_id,
                c.title AS channel_title,
                c.username AS channel_username,
                lt.target_quantity,
                lt.status,
                lt.created_at,
                lt.updated_at
            FROM live_tasks lt
            JOIN channels c ON c.id = lt.channel_id
            ORDER BY lt.id DESC
            """
        )

    return [dict(row) for row in rows]


async def set_live_task_status(task_id: int, status: str) -> bool:
    """Change a live task's status."""
    if status not in {"running", "stopped"}:
        raise ValueError("Status must be 'running' or 'stopped'.")

    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE live_tasks
            SET status = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            status,
            task_id,
        )

    return result == "UPDATE 1"
