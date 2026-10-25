
from database import get_pool


async def init_live_campaign_schema() -> None:
    """Create storage for per-channel live campaign settings."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_campaign_settings (
                group_id BIGINT PRIMARY KEY
                    REFERENCES groups(id) ON DELETE CASCADE,
                target_viewers INTEGER NOT NULL DEFAULT 100
                    CHECK (target_viewers BETWEEN 1 AND 100000),
                service_active BOOLEAN NOT NULL DEFAULT FALSE,
                stream_status TEXT NOT NULL DEFAULT 'unknown'
                    CHECK (
                        stream_status IN (
                            'unknown', 'live', 'offline'
                        )
                    ),
                last_event_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


async def set_live_quantity(
    group_id: int,
    quantity: int,
) -> bool:
    """Set the campaign target for a registered target group."""
    if not 1 <= quantity <= 100000:
        raise ValueError("Quantity must be between 1 and 100000.")

    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            INSERT INTO live_campaign_settings (
                group_id, target_viewers
            )
            SELECT id, $2
            FROM groups
            WHERE id = $1
              AND group_type = 'target'
            ON CONFLICT (group_id)
            DO UPDATE SET
                target_viewers = EXCLUDED.target_viewers,
                updated_at = NOW()
            RETURNING group_id
            """,
            group_id,
            quantity,
        )

    return result is not None


async def set_service_active(
    group_id: int,
    enabled: bool,
) -> bool:
    """Turn a registered group's campaign service on or off."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            INSERT INTO live_campaign_settings (
                group_id, service_active
            )
            SELECT id, $2
            FROM groups
            WHERE id = $1
              AND group_type = 'target'
            ON CONFLICT (group_id)
            DO UPDATE SET
                service_active = EXCLUDED.service_active,
                updated_at = NOW()
            RETURNING group_id
            """,
            group_id,
            enabled,
        )

    return result is not None


async def get_live_settings(group_id: int):
    """Return the saved campaign settings for a group."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT
                g.id AS group_id,
                g.title,
                g.is_active AS group_is_active,
                COALESCE(s.target_viewers, 100)
                    AS target_viewers,
                COALESCE(s.service_active, FALSE)
                    AS service_active,
                COALESCE(s.stream_status, 'unknown')
                    AS stream_status,
                s.last_event_at,
                s.updated_at
            FROM groups AS g
            LEFT JOIN live_campaign_settings AS s
                ON s.group_id = g.id
            WHERE g.id = $1
              AND g.group_type = 'target'
            """,
            group_id,
        )


async def record_stream_status(
    group_id: int,
    status: str,
) -> bool:
    """
    Save a stream status reported by a trusted event source.
    This function does not detect streams by itself.
    """
    if status not in {"live", "offline", "unknown"}:
        raise ValueError("Invalid stream status.")

    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            INSERT INTO live_campaign_settings (
                group_id, stream_status, last_event_at
            )
            SELECT id, $2, NOW()
            FROM groups
            WHERE id = $1
              AND group_type = 'target'
            ON CONFLICT (group_id)
            DO UPDATE SET
                stream_status = EXCLUDED.stream_status,
                last_event_at = NOW(),
                updated_at = NOW()
            RETURNING group_id
            """,
            group_id,
            status,
        )

    return result is not None
