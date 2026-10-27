
import asyncpg
import json
import logging

from config import DATABASE_URL, OWNER_ADMIN_ID

logger = logging.getLogger(__name__)

_pool = None


async def connect_db():
    """Create the PostgreSQL connection pool."""
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )

    return _pool


async def get_pool():
    """Return the active PostgreSQL pool."""
    global _pool

    if _pool is None:
        return await connect_db()

    return _pool


async def close_db():
    """Close the PostgreSQL pool."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


async def init_database():
    """Create the bot's database tables."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                role TEXT NOT NULL DEFAULT 'sub_admin',
                permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
                added_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_configs (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                api_id BIGINT NOT NULL,
                api_hash_encrypted TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id BIGSERIAL PRIMARY KEY,
                label TEXT NOT NULL,
                phone_number TEXT,
                session_data TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                username TEXT,
                title TEXT,
                channel_link TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS live_tasks (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                target_quantity INTEGER NOT NULL DEFAULT 0
                    CHECK (target_quantity >= 0),
                status TEXT NOT NULL DEFAULT 'stopped',
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reaction_tasks (
                id BIGSERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL
                    REFERENCES channels(id) ON DELETE CASCADE,
                reaction_type TEXT NOT NULL DEFAULT 'default',
                target_quantity INTEGER NOT NULL DEFAULT 0
                    CHECK (target_quantity >= 0),
                status TEXT NOT NULL DEFAULT 'stopped',
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id BIGSERIAL PRIMARY KEY,
                actor_id BIGINT,
                action TEXT NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at
            ON activity_logs (created_at DESC)
        """)

        await conn.execute("""
            INSERT INTO admins (user_id, role, permissions)
            VALUES ($1, 'owner', '{"all": true}'::jsonb)
            ON CONFLICT (user_id)
            DO UPDATE SET
                role = 'owner',
                permissions = '{"all": true}'::jsonb
        """, OWNER_ADMIN_ID)

    logger.info("Database initialization completed.")


async def log_database_error(action: str, details: dict | None = None):
    """Save an activity or error record."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO activity_logs (action, details)
            VALUES ($1, $2::jsonb)
            """,
            action,
            json.dumps(details or {}),
        )
