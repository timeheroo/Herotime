
"""Reusable authentication and authorization dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_telegram_user
from config import OWNER_ID
from database.connection import get_session
from database.models import AdminPermission, User


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Provide a database session to an API request."""
    async for session in get_session():
        yield session


DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


async def get_authenticated_user(
    telegram_user: Annotated[
        dict,
        Depends(get_current_telegram_user),
    ],
    session: DatabaseSession,
) -> User:
    """Require a verified and active database user."""

    telegram_id = telegram_user.get("id")

    if not isinstance(telegram_id, int) or isinstance(telegram_id, bool):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram user identity.",
        )

    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )

    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not registered or is inactive.",
        )

    return user


async def require_owner(
    user: Annotated[
        User,
        Depends(get_authenticated_user),
    ],
) -> User:
    """Allow only the configured owner."""

    if user.telegram_id != OWNER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required.",
        )

    return user


def require_permission(permission: str):
    """Create a dependency for checking individual admin permissions."""

    if not permission or not permission.strip():
        raise ValueError("Permission name cannot be empty.")

    permission = permission.strip()

    async def permission_checker(
        user: Annotated[
            User,
            Depends(get_authenticated_user),
        ],
        session: DatabaseSession,
    ) -> User:
        # Owner always has full access.
        if user.telegram_id == OWNER_ID:
            return user

        if user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required.",
            )

        result = await session.execute(
            select(AdminPermission.is_enabled).where(
                AdminPermission.user_id == user.id,
                AdminPermission.permission == permission,
            )
        )

        enabled = result.scalar_one_or_none()

        if enabled is not True:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission for this action.",
            )

        return user

    return permission_checker
