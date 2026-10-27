
import json
import logging

from database import get_pool

logger = logging.getLogger(__name__)


async def log_action(
    actor_id: int,
    action: str,
    details: dict | None = None,
) -> bool:
    """Record an admin action without storing secrets."""
    pool = await get_pool()

    safe_details = details or {}

    # Avoid logging API credentials or session secrets.
    sensitive_keys = {
        "api_hash",
        "api_hash_encrypted",
        "bot_token",
        "password",
        "session_data",
        "session_string",
        "token",
    }

    filtered_details = {
        key: value
        for key, value in safe_details.items()
        if key.lower() not in sensitive_keys
    }

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_logs (actor_id, action, details)
                VALUES ($1, $2, $3::jsonb)
                """,
                actor_id,
                action,
                json.dumps(filtered_details, default=str),
            )

        return True

    except Exception:
        logger.exception("Failed to record admin action: %s", action)
        return False
