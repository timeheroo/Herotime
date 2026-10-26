
from datetime import timedelta

from database import get_pool


REPORT_PERIODS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "24h": timedelta(hours=24),
    "72h": timedelta(hours=72),
}


async def get_report(period: str) -> dict:
    """Return task and activity counts for a supported period."""
    period = period.strip().lower()

    if period not in REPORT_PERIODS:
        raise ValueError(
            "Invalid period. Choose: daily, weekly, monthly, 24h, or 72h."
        )

    pool = get_pool()
    interval = REPORT_PERIODS[period]

    async with pool.acquire() as conn:
        channels_added = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM channels
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        live_tasks_created = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM live_tasks
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        reaction_tasks_created = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM reaction_tasks
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

        activity_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM activity_logs
            WHERE created_at >= NOW() - $1
            """,
            interval,
        )

    return {
        "period": period,
        "channels_added": channels_added,
        "live_tasks_created": live_tasks_created,
        "reaction_tasks_created": reaction_tasks_created,
        "activity_count": activity_count,
    }


async def get_recent_activity(limit: int = 20) -> list[dict]:
    """Return recent audit-log entries."""
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, actor_id, action, details, created_at
            FROM activity_logs
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

    return [dict(row) for row in rows]
