
"""Authenticated channel management API routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DatabaseSession, require_permission
from database.models import Channel, User

router = APIRouter(prefix="/channels", tags=["Channels"])

ChannelManager = Annotated[
    User,
    __import__("fastapi").Depends(require_permission("channel_management")),
]


class ChannelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    chat_link: str | None = Field(default=None, max_length=500)
    chat_type: str = Field(
        default="channel",
        pattern=r"^(channel|group|supergroup)$",
    )


class ChannelResponse(BaseModel):
    id: int
    title: str
    username: str | None
    chat_link: str | None
    chat_type: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_channel(
    payload: ChannelCreate,
    _user: ChannelManager,
    session: DatabaseSession,
):
    """Register channel details in the database."""
    username = (
        payload.username.strip().lstrip("@")
        if payload.username
        else None
    )
    link = payload.chat_link.strip() if payload.chat_link else None
    title = payload.title.strip()

    if not title:
        raise HTTPException(
            status_code=422,
            detail="Title cannot be empty.",
        )

    if username:
        result = await session.execute(
            select(Channel).where(Channel.username == username)
        )
        if result.scalar_one_or_none():
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
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Channel conflicts with an existing database record.",
        ) from exc

    return channel


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    _user: ChannelManager,
    active_only: bool = Query(default=False),
    session: DatabaseSession = None,
):
    """List registered channels."""
    statement = select(Channel).order_by(Channel.id.desc())

    if active_only:
        statement = statement.where(Channel.is_active.is_(True))

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.patch(
    "/{channel_id}/deactivate",
    response_model=ChannelResponse,
)
async def deactivate_channel(
    channel_id: int,
    _user: ChannelManager,
    session: DatabaseSession,
):
    """Deactivate a registered channel."""
    channel = await session.get(Channel, channel_id)

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    channel.is_active = False
    await session.commit()
    await session.refresh(channel)
    return channel


@router.patch(
    "/{channel_id}/reactivate",
    response_model=ChannelResponse,
)
async def reactivate_channel(
    channel_id: int,
    _user: ChannelManager,
    session: DatabaseSession,
):
    """Reactivate a registered channel."""
    channel = await session.get(Channel, channel_id)

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    channel.is_active = True
    await session.commit()
    await session.refresh(channel)
    return channel
