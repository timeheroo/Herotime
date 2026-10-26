
from database import get_pool


VALID_STREAM_STATUSES = {"unknown", "live", "offline", "error"}


async def init_live_campaign_schema() -> None:
    """Create live campaign settings without deleting existing records."""
    pool = get_pool()

    if pool is None:
        raise RuntimeError(
            "Database pool is not initialized. Call init_db() first."
        )

    async with pool.acquire() as conn:
        # This table stores settings, not actual viewer counts.
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
                            'unknown', 'live', 'offline', 'error'
                        )
                    ),
                last_event_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


async def set_live_quantity(group_id: int, quantity: int) -> None:
    """Set the target quantity for a registered target group."""
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise ValueError("Quantity must be a whole number.")

    if not 1 <= quantity <= 100000:
        raise ValueError("Quantity must be between 1 and 100000.")

    pool = get_pool()

    if pool is None:
        raise RuntimeError("Database is not initialized.")

    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            """
            SELECT id, group_type
            FROM groups
            WHERE id = $1
            """,
            group_id,
        )

        if not group:
            raise ValueError(f"Group ID {group_id} was not found.")

        if group["group_type"] != "target":
            raise ValueError(
                "Quantity can only be set for a group whose type is "
                "'target'. This group is registered as "
                f"'{group['group_type']}'."
            )

        await conn.execute(
            """
            INSERT INTO live_campaign_settings
                (group_id, target_viewers, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (group_id)
            DO UPDATE SET
                target_viewers = EXCLUDED.target_viewers,
                updated_at = NOW()
            """,
            group_id,
            quantity,
        )


async def set_service_active(group_id: int, enabled: bool) -> None:
    """Enable or disable service for a group in both settings tables."""
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be True or False.")

    pool = get_pool()

    if pool is None:
        raise RuntimeError("Database is not initialized.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            group = await conn.fetchrow(
                """
                SELECT id
                FROM groups
                WHERE id = $1
                FOR UPDATE
                """,
                group_id,
            )

            if not group:
                raise ValueError(f"Group ID {group_id} was not found.")

            # Keep the group-level service flag in sync.
            await conn.execute(
                """
                UPDATE groups
                SET service_active = $2
                WHERE id = $1
                """,
                group_id,
                enabled,
            )

            # Create settings if they do not exist yet.
            await conn.execute(
                """
                INSERT INTO live_campaign_settings
                    (group_id, service_active, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (group_id)
                DO UPDATE SET
                    service_active = EXCLUDED.service_active,
                    updated_at = NOW()
                """,
                group_id,
                enabled,
            )


async def get_live_settings(group_id: int):
    """Return settings used by live_admin.py, or None if absent."""
    pool = get_pool()

    if pool is None:
        raise RuntimeError("Database is not initialized.")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                g.id AS group_id,
                g.title,
                g.service_active AS group_is_active,
                s.target_viewers,
                s.service_active,
                s.stream_status,
                s.last_event_at
            FROM groups AS g
            LEFT JOIN live_campaign_settings AS s
                ON s.group_id = g.id
            WHERE g.id = $1
            """,
            group_id,
        )

    if not row:
        return None

    result = dict(row)

    # A group can exist before live settings have been created.
    if result["target_viewers"] is None:
        result["target_viewers"] = 100

    if result["service_active"] is None:
        result["service_active"] = False

    if result["stream_status"] is None:
        result["stream_status"] = "unknown"

    return result


async def record_stream_status(group_id: int, status: str) -> None:
    """Record a stream status reported by a trusted monitoring process."""
    if status not in VALID_STREAM_STATUSES:
        raise ValueError(
            "Invalid stream status. Use: "
            + ", ".join(sorted(VALID_STREAM_STATUSES))
        )

    pool = get_pool()

    if pool is None:
        raise RuntimeError("Database is not initialized.")

    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            "SELECT id FROM groups WHERE id = $1",
            group_id,
        )

        if not group:
            raise ValueError(f"Group ID {group_id} was not found.")

        await conn.execute(
            """
            INSERT INTO live_campaign_settings
                (group_id, stream_status, last_event_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (group_id)
            DO UPDATE SET
                stream_status = EXCLUDED.stream_status,
                last_event_at = NOW(),
                updated_at = NOW()
            """,
            group_id,
            status,
        )
