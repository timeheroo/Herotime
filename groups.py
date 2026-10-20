import logging
from urllib.parse import urlparse

from database import get_pool

logger = logging.getLogger(name)


VALID_GROUP_TYPES = {"source", "target"}


def validate_invite_url(url: str | None) -> str | None:
    """Accept only Telegram HTTPS invite links."""
    if url is None or not url.strip():
        return None

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("Invite links must use HTTPS.")

    if parsed.hostname not in {
        "t.me",
        "www.t.me",
        "telegram.me",
        "www.telegram.me",
    }:
        raise ValueError("URL must be a Telegram link.")

    if parsed.username or parsed.password or parsed.port:
        raise ValueError("Invalid Telegram invite URL.")

    return url


async def add_group(
    owner_user_id: int,
    title: str,
    group_type: str,
    telegram_chat_id: int | None = None,
    invite_url: str | None = None,
    consent_verified: bool = False,
):
    """Save a group the user is authorized to manage."""
    title = title.strip()

    if not title:
        raise ValueError("Group title is required.")

    if group_type not in VALID_GROUP_TYPES:
        raise ValueError("Group type must be source or target.")

    invite_url = validate_invite_url(invite_url)

    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            owner = await conn.fetchrow(
                """
                SELECT id, status
                FROM users
                WHERE id = $1
                FOR UPDATE
                """,
                owner_user_id,
            )

            if owner is None or owner["status"] != "approved":
                raise PermissionError(
                    "Only approved users can add group records."
                )

            row = await conn.fetchrow(
                """
                INSERT INTO groups (
                    owner_user_id,
                    telegram_chat_id,
                    title,
                    group_type,
                    invite_url,
                    consent_verified
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                owner_user_id,
                telegram_chat_id,
                title,
                group_type,
                invite_url,
                consent_verified,
            )

            return dict(row)


async def list_groups(
    owner_user_id: int,
    group_type: str | None = None,
):
    """List group records belonging to a user."""
    if group_type is not None and group_type not in VALID_GROUP_TYPES:
        raise ValueError("Invalid group type.")

    pool = get_pool()

    async with pool.acquire() as conn:
        if group_type:
            rows = await conn.fetch(
                """
                SELECT id, title, telegram_chat_id, group_type,
                       invite_url, consent_verified, created_at
                FROM groups
                WHERE owner_user_id = $1
                  AND group_type = $2
                ORDER BY created_at DESC
                """,
                owner_user_id,
                group_type,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, title, telegram_chat_id, group_type,
                       invite_url, consent_verified, created_at
                FROM groups
                WHERE owner_user_id = $1
                ORDER BY created_at DESC
                """,
                owner_user_id,
            )

        return [dict(row) for row in rows]


async def get_group(
    owner_user_id: int,
    group_id: int,
):
    """Fetch a group only if it belongs to the requesting user."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM groups
            WHERE id = $1
              AND owner_user_id = $2
            """,
            group_id,
            owner_user_id,
        )

        return dict(row) if row else None


async def update_invite_link(
    owner_user_id: int,
    group_id: int,
    invite_url: str | None,
):
    """Update a saved Telegram invite link."""
    invite_url = validate_invite_url(invite_url)

    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE groups
            SET invite_url = $3
            WHERE id = $1
              AND owner_user_id = $2
            RETURNING id, title, invite_url
            """,
            group_id,
            owner_user_id,
            invite_url,
        )

        return dict(row) if row else None


async def delete_group(
    owner_user_id: int,
    group_id: int,
):
    """Delete a group record belonging to the requesting user."""
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            active_task = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM tasks
                    WHERE target_group_id = $1
                      AND status IN ('queued', 'running', 'paused')
                )
                """,
                group_id,
            )

            if active_task:
                raise ValueError(
                    "Cannot delete a group linked to an active task."
                )

            result = await conn.execute(
                """
                DELETE FROM groups
                WHERE id = $1
                  AND owner_user_id = $2
                """,
                group_id,
                owner_user_id,
            )

            return result == "DELETE 1"
