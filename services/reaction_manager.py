
from database import get_pool


ALLOWED_REACTIONS = {
    "like": "👍",
    "heart": "❤️",
    "fire": "🔥",
    "thumbsup": "👍",
    "laugh": "😄",
    "sad": "😢",
    "wow": "😮",
}


async def create_reaction_task(
    channel_id: int,
    reaction_type: str,
    target_quantity: int,
    created_by: int,
):
    """Save a reaction-task configuration."""
    reaction_type = reaction_type.strip().lower()

    if reaction_type not in ALLOWED_REACTIONS:
        raise ValueError(
            "Unsupported reaction. Choose: "
            + ", ".join(sorted(ALLOWED_REACTIONS))
        )

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
            INSERT INTO reaction_tasks
                (channel_id, reaction_type, target_quantity, status, created_by)
            VALUES ($1, $2, $3, 'stopped', $4)
            RETURNING id, channel_id, reaction_type,
                      target_quantity, status, created_at
            """,
            channel_id,
            reaction_type,
            target_quantity,
            created_by,
        )

    return dict(row)


async def list_reaction_tasks():
    """List saved reaction-task configurations."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                rt.id,
                rt.channel_id,
                c.title AS channel_title,
                c.username AS channel_username,
                rt.reaction_type,
                rt.target_quantity,
                rt.status,
                rt.created_at,
                rt.updated_at
            FROM reaction_tasks rt
            JOIN channels c ON c.id = rt.channel_id
            ORDER BY rt.id DESC
            """
        )

    return [dict(row) for row in rows]


async def set_reaction_task_status(task_id: int, status: str) -> bool:
    """Start or stop a saved task configuration."""
    if status not in {"running", "stopped"}:
        raise ValueError("Status must be 'running' or 'stopped'.")

    pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE reaction_tasks
            SET status = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            status,
            task_id,
        )

    return result == "UPDATE 1"
