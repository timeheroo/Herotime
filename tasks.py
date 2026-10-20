import logging

from database import get_pool, log_task

logger = logging.getLogger(name)

ACTIVE_STATUSES = {"queued", "running", "paused"}

VALID_TASK_TYPES = {
    "invite_link",
    "approved_announcement",
    "membership_report",
}


async def create_task(
    owner_user_id: int,
    task_type: str,
    target_group_id: int | None = None,
):
    """Create a task for an approved user."""
    if task_type not in VALID_TASK_TYPES:
        raise ValueError("Unsupported task type.")

    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                """
                SELECT id, status
                FROM users
                WHERE id = $1
                FOR UPDATE
                """,
                owner_user_id,
            )

            if user is None or user["status"] != "approved":
                raise PermissionError("User is not approved.")

            if target_group_id is not None:
                group = await conn.fetchrow(
                    """
                    SELECT id
                    FROM groups
                    WHERE id = $1
                      AND owner_user_id = $2
                      AND group_type = 'target'
                    """,
                    target_group_id,
                    owner_user_id,
                )

                if group is None:
                    raise ValueError(
                        "Target group not found or not owned by user."
                    )

            task = await conn.fetchrow(
                """
                INSERT INTO tasks (
                    owner_user_id,
                    target_group_id,
                    task_type,
                    status
                )
                VALUES ($1, $2, $3, 'queued')
                RETURNING *
                """,
                owner_user_id,
                target_group_id,
                task_type,
            )

    await log_task(task["id"], "Task created.")
    return dict(task)


async def get_task(task_id: int):
    """Fetch a task by its database ID."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tasks WHERE id = $1",
            task_id,
        )

        return dict(row) if row else None


async def list_user_tasks(
    owner_user_id: int,
    limit: int = 10,
):
    """Return recent tasks for one user."""
    limit = max(1, min(limit, 100))
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM tasks
            WHERE owner_user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            owner_user_id,
            limit,
        )

        return [dict(row) for row in rows]


async def list_active_tasks(limit: int = 100):
    """Return tasks that are queued, running or paused."""
    limit = max(1, min(limit, 500))
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM tasks
            WHERE status = ANY($1::text[])
            ORDER BY created_at ASC
            LIMIT $2
            """,
            list(ACTIVE_STATUSES),
            limit,
        )

        return [dict(row) for row in rows]


async def change_task_status(
    task_id: int,
    new_status: str,
    owner_user_id: int | None = None,
):
    """Change a task status with ownership checks."""
    allowed = {
        "running",
        "paused",
        "completed",
        "failed",
        "cancelled",
    }

    if new_status not in allowed:
        raise ValueError("Invalid task status.")

    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            if owner_user_id is None:
                task = await conn.fetchrow(
                    """
                    SELECT *
                    FROM tasks
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    task_id,
                )
            else:
                task = await conn.fetchrow(
                    """
                    SELECT *
                    FROM tasks
                    WHERE id = $1
                      AND owner_user_id = $2
                    FOR UPDATE
                    """,
                    task_id,
                    owner_user_id,
                )

            if task is None:
                raise ValueError("Task not found.")

            current = task["status"]

            transitions = {
                "queued": {"running", "cancelled"},
                "running": {
                    "paused", "completed", "failed", "cancelled"
                },
                "paused": {"running", "cancelled"},
                "completed": set(),
                "failed": set(),
                "cancelled": set(),
            }

            if new_status not in transitions.get(current, set()):
                raise ValueError(
                    f"Cannot change task from {current} "
                    f"to {new_status}."
                )

            updated = await conn.fetchrow(
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
                new_status,
            )

    await log_task(
        task_id,
        f"Task status changed from {current} to {new_status}.",
    )

    return dict(updated)


async def update_task_progress(
    task_id: int,
    processed_count: int,
    total_count: int,
    error_count: int = 0,
):
    """Update progress counters for a task."""
    if min(processed_count, total_count, error_count) < 0:
        raise ValueError("Progress values cannot be negative.")

    if processed_count > total_count:
        raise ValueError("Processed count exceeds total count.")

    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE tasks
            SET processed_count = $2,
                total_count = $3,
                error_count = $4
            WHERE id = $1
              AND status = 'running'
            RETURNING *
            """,
            task_id,
            processed_count,
            total_count,
            error_count,
        )

        if row is None:
            raise ValueError(
                "Task not found or task is not running."
            )

        result = dict(row)

    await log_task(
        task_id,
        f"Progress: {processed_count}/{total_count}; "
        f"errors: {error_count}.",
    )

    return result


async def task_statistics():
    """Return aggregate task statistics for the admin panel."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE status = 'queued'
                ) AS queued,
                COUNT(*) FILTER (
                    WHERE status = 'running'
                ) AS running,
                COUNT(*) FILTER (
                    WHERE status = 'paused'
                ) AS paused,
                COUNT(*) FILTER (
                    WHERE status = 'completed'

) AS completed,
                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed,
                COUNT(*) FILTER (
                    WHERE status = 'cancelled'
                ) AS cancelled
            FROM tasks
            """
        )

        return dict(row)
