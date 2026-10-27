
"""API endpoints for channel management."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import (
    DatabaseSession,
    get_authenticated_user,
    require_permission,
)
from database.models import Channel, User


router = APIRouter(prefix="/channels", tags=["Channels"])


class ChannelCreate(BaseModel):
    telegram_chat_id: int
    title: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    chat_type: Literal["channel", "group", "supergroup"] = "channel"


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_chat_id: int
    title: str
    username: str | None
    chat_type: str
    is_active: bool


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """List active channels for authenticated users."""
    result = await session.execute(
        select(Channel)
        .where(Channel.is_active.is_(True))
        .order_by(Channel.id.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    payload: ChannelCreate,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("channels.manage"))],
):
    """Register a channel in the database."""
    channel = Channel(
        telegram_chat_id=payload.telegram_chat_id,
        title=payload.title.strip(),
        username=payload.username,
        chat_type=payload.chat_type,
        created_by_user_id=user.id,
        is_active=True,
    )

    session.add(channel)

    try:
        await session.commit()
        await session.refresh(channel)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A channel with this Telegram chat ID may already exist.",
        )

    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_200_OK)
async def deactivate_channel(
    channel_id: int,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("channels.manage"))],
):
    """Deactivate a channel without permanently deleting its record."""
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )

    channel.is_active = False
    await session.commit()

    return {
        "success": True,
        "message": "Channel deactivated.",
        "channel_id": channel.id,
    }
