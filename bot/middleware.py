
"""User registration and access-control helpers."""

import logging

from pyrogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import OWNER_ID
from database.models import User
from database.repositories import create_user

logger = logging.getLogger(__name__)


async def register_telegram_user(
    session: AsyncSession,
    message: Message,
) -> User | None:
    """Register or refresh the sender's database profile."""
    sender = message.from_user

    if sender is None:
        return None

    display_name = " ".join(
        part
        for part in [sender.first_name, sender.last_name]
        if part
    )

    try:
        user = await create_user(
            session=session,
            telegram_id=sender.id,
            username=sender.username,
            display_name=display_name or None,
        )

        # Keep the configured owner role synchronized.
        if sender.id == OWNER_ID and user.role != "admin":
            user.role = "admin"
            await session.commit()
            await session.refresh(user)

        return user

    except Exception:
        await session.rollback()
        logger.exception(
            "Failed to register Telegram user %s",
            sender.id,
        )
        return None


def is_owner(telegram_id: int | None) -> bool:
    """Return True when the Telegram ID belongs to the owner."""
    return telegram_id == OWNER_ID


async def user_is_active(
    session: AsyncSession,
    telegram_id: int,
) -> bool:
    """Check whether a registered user is active."""
    from sqlalchemy import select

    result = await session.execute(
        select(User.is_active).where(User.telegram_id == telegram_id)
    )
    active = result.scalar_one_or_none()

    return bool(active)


async def user_has_permission(
    session: AsyncSession,
    telegram_id: int,
    permission: str,
) -> bool:
    """Check the owner's access or an admin's explicit permission."""
    from sqlalchemy import select

    if is_owner(telegram_id):
        return True

    result = await session.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.is_active.is_(True),
            User.role == "admin",
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        return False

    from database.models import AdminPermission

    permission_result = await session.execute(
        select(AdminPermission.is_enabled).where(
            AdminPermission.user_id == user.id,
            AdminPermission.permission == permission,
        )
    )

    enabled = permission_result.scalar_one_or_none()
    return enabled is True
