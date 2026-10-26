
import logging
from typing import Any

from database import get_pool

logger = logging.getLogger(__name__)


async def log_action(
    actor_id: int,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Save an administrative action to the PostgreSQL audit log."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO activity_logs (
                actor_id,
                action,
                details
            )
            VALUES ($1, $2, $3::jsonb)
            """,
            actor_id,
            action,
            __import__("json").dumps(details or {}),
        )

    logger.info(
        "Administrative action recorded: actor_id=%s action=%s",
        actor_id,
        action,
    )
