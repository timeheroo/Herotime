
"""Channel management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import Channel

router = APIRouter(prefix="/channels", tags=["Channels"])


class ChannelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    chat_link: str | None = Field(default=None, max_length=500)
    chat_type: str = Field(default="channel", pattern="^(channel|group|supergroup)$")


class ChannelResponse(BaseModel):
    id: int
    title: str
    username: str | None
    chat_link: str | None
    chat_type: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=ChannelResponse, status_code=201)
async def add_channel(
    payload: ChannelCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a channel by its supplied details."""
    username = payload.username.strip().lstrip("@") if payload.username else None
    link = payload.chat_link.strip() if payload.chat_link else None
    title = payload.title.strip()

    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty.")

    if username:
        result = await session.execute(
            select(Channel).where(Channel.username == username)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="A channel with this username is already registered.",
            )

    channel = Channel(
        title=title,
        username=username,
        chat_link=link,
        chat_type=payload.chat_type,
        is_active=True,
    )

    session.add(channel)

    try:
        await session.commit()
        await session.refresh(channel)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Channel conflicts with an existing database record.",
        )

    return channel


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    active_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    """List registered channels."""
    statement = select(Channel).order_by(Channel.id.desc())

    if active_only:
        statement = statement.where(Channel.is_active.is_(True))

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.patch("/{channel_id}/deactivate", response_model=ChannelResponse)
async def deactivate_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Deactivate a registered channel."""
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    channel.is_active = False
    await session.commit()
    await session.refresh(channel)
    return channel


@router.patch("/{channel_id}/reactivate", response_model=ChannelResponse)
async def reactivate_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reactivate a registered channel."""
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    channel.is_active = True
    await session.commit()
    await session.refresh(channel)
    return channel
