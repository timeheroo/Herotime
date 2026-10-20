import json
import logging
from contextlib import asynccontextmanager

import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(name)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'user'
        CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'banned')),
    credits INTEGER NOT NULL DEFAULT 0 CHECK (credits >= 0),
    subscription_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS groups (
    id BIGSERIAL PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id),
    telegram_chat_id BIGINT,
    title TEXT NOT NULL,
    group_type TEXT NOT NULL
        CHECK (group_type IN ('source', 'target')),
    invite_url TEXT,
    consent_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES users(id),
    target_group_id BIGINT REFERENCES groups(id),
    task_type TEXT NOT NULL
        CHECK (task_type IN (
            'invite_link',
            'approved_announcement',
            'membership_report'
        )),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN (
            'queued', 'running', 'paused',
            'completed', 'failed', 'cancelled'
        )),
    total_count INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    task_id BIGINT REFERENCES tasks(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_logs (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id),
    level TEXT NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT REFERENCES users(id),
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_status
    ON users(status);

CREATE INDEX IF NOT EXISTS idx_groups_owner
    ON groups(owner_user_id);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created
    ON tasks(status, created_at);

CREATE INDEX IF NOT EXISTS idx_task_logs_task
    ON task_logs(task_id, created_at);
"""


_pool = None


async def init_db():
    """Create the connection pool and initialize database tables."""
    global _pool

    if _pool is not None:
        return

    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )

    try:
        async with _pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)

        logger.info("Database initialized successfully.")

    except Exception:
        await _pool.close()
        _pool = None
        logger.exception("Database initialization failed.")
        raise


async def close_db():
    """Close the database pool during application shutdown."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed.")


def get_pool():
    """Return the initialized connection pool."""
    if _pool is None:
        raise RuntimeError(
            "Database is not initialized. Call init_db() first."
        )

    return _pool


@asynccontextmanager
async def connection():
    """Acquire a database connection."""
    pool = get_pool()

    async with pool.acquire() as conn:
        yield conn


async def register_user(
    telegram_id: int,
    username: str | None = None,
    display_name: str | None = None,
    is_admin: bool = False,
):
    """
    Register a Telegram user.

    New regular users require approval.
    Configured admins receive the admin role.
    Existing banned users remain banned.
    """
    role = "admin" if is_admin else "user"
    status = "approved" if is_admin else "pending"

    async with connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (
                telegram_id, username, display_name, role, status
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                role = CASE
                    WHEN EXCLUDED.role = 'admin' THEN 'admin'
                    ELSE users.role
                END,
                status = CASE
                    WHEN EXCLUDED.role = 'admin' THEN 'approved'
                    ELSE users.status
                END
            RETURNING *
            """,
            telegram_id,
            username,
            display_name,
            role,
            status,
        )

        return dict(row)


async def get_user(telegram_id: int):
    """Find a user by Telegram ID."""
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE telegram_id = $1
            """,
            telegram_id,
        )

        return dict(row) if row else None


async def set_user_status(
    user_id: int,
    status: str,
):
    """Approve or ban a user."""
    if status not in {"pending", "approved", "banned"}:
        raise ValueError("Invalid user status.")

    async with connection() as conn:
        return await conn.fetchrow(
            """
            UPDATE users
            SET status = $2
            WHERE id = $1
            RETURNING id, telegram_id, status
            """,
            user_id,
            status,
        )


async def list_users(
    status: str | None = None,
    limit: int = 50,
):
    """List users, optionally filtered by status."""
    limit = max(1, min(limit, 200))

    async with connection() as conn:
        if status is None:
            rows = await conn.fetch(
                """
                SELECT id, telegram_id, username, role,
                       status, credits, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            if status not in {"pending", "approved", "banned"}:
                raise ValueError("Invalid user status.")

            rows = await conn.fetch(
                """
                SELECT id, telegram_id, username, role,
                       status, credits, created_at
                FROM users
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                status,
                limit,
            )

        return [dict(row) for row in rows]


async def adjust_credits(
    user_id: int,
    amount: int,
    reason: str,
):
    """
    Add or deduct credits atomically.
    Negative balances are not permitted.
    """
    if amount == 0:
        raise ValueError("Credit adjustment cannot be zero.")

    if not reason.strip():
        raise ValueError("A reason is required.")

    async with connection() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE users
                SET credits = credits + $2
                WHERE id = $1
                  AND credits + $2 >= 0
                RETURNING id, telegram_id, credits
                """,
                user_id,
                amount,
            )

if row is None:
                raise ValueError(
                    "User not found or insufficient credits."
                )

            await conn.execute(
                """
                INSERT INTO credit_transactions (
                    user_id, amount, reason
                )
                VALUES ($1, $2, $3)
                """,
                user_id,
                amount,
                reason.strip(),
            )

            return dict(row)


async def create_task(
    owner_user_id: int,
    task_type: str,
    target_group_id: int | None = None,
):
    """Create a queued, consent-based community task."""
    allowed_types = {
        "invite_link",
        "approved_announcement",
        "membership_report",
    }

    if task_type not in allowed_types:
        raise ValueError("Unsupported task type.")

    async with connection() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO tasks (
                owner_user_id, task_type, target_group_id
            )
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            owner_user_id,
            task_type,
            target_group_id,
        )


async def update_task_status(
    task_id: int,
    status: str,
):
    """Update task status."""
    allowed_statuses = {
        "queued", "running", "paused",
        "completed", "failed", "cancelled",
    }

    if status not in allowed_statuses:
        raise ValueError("Invalid task status.")

    async with connection() as conn:
        return await conn.fetchrow(
            """
            UPDATE tasks
            SET status = $2,
                started_at = CASE
                    WHEN $2 = 'running'
                    THEN COALESCE(started_at, NOW())
                    ELSE started_at
                END,
                completed_at = CASE
                    WHEN $2 IN ('completed', 'failed', 'cancelled')
                    THEN NOW()
                    ELSE NULL
                END
            WHERE id = $1
            RETURNING *
            """,
            task_id,
            status,
        )


async def log_task(
    task_id: int,
    message: str,
    level: str = "INFO",
):
    """Write a task event to the log."""
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO task_logs (task_id, level, message)
            VALUES ($1, $2, $3)
            """,
            task_id,
            level.upper(),
            message,
        )


async def audit_action(
    actor_user_id: int | None,
    action: str,
    details: dict | None = None,
):
    """Record an administrative action."""
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (
                actor_user_id, action, details
            )
            VALUES ($1, $2, $3::jsonb)
            """,
            actor_user_id,
            action,
            json.dumps(details or {}),
        )
