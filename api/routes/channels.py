
"""Authenticated channel management API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DatabaseSession, require_permission
from database.models import Channel, User


router = APIRouter(
    prefix="/channels",
    tags=["Channels"],
)


ChannelManager = Annotated[
    User,
    Depends(require_permission("channel_management")),
]


class ChannelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    chat_link: str | None = Field(default=None, max_length=500)
    chat_type: str = Field(
        default="channel",
        pattern=r"^(channel|group|supergroup)$",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Channel title cannot be empty.")

        return value

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().lstrip("@")

        if not value:
            return None

        return value.lower()

    @field_validator("chat_link")
    @classmethod
    def normalize_chat_link(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


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
    user: ChannelManager,
    session: DatabaseSession,
) -> Channel:
    """Register channel metadata in the database."""

    title = payload.title
    username = payload.username
    chat_link = payload.chat_link

    if username:
        result = await session.execute(
            select(Channel.id).where(
                func.lower(Channel.username) == username
            )
        )

        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A channel with this username is already registered.",
            )

    channel = Channel(
        title=title,
        username=username,
        chat_link=chat_link,
        chat_type=payload.chat_type,
        is_active=True,
        created_by_user_id=user.id,
    )

    session.add(channel)

    try:
        await session.commit()
        await session.refresh(channel)

    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel conflicts with an existing database record.",
        ) from exc

    return channel


@router.get(
    "",
    response_model=list[ChannelResponse],
)
async def list_channels(
    _user: ChannelManager,
    session: DatabaseSession,
    active_only: bool = Query(default=False),
) -> list[Channel]:
    """List registered channels."""

    statement = select(Channel).order_by(
        Channel.id.desc()
    )

    if active_only:
        statement = statement.where(
            Channel.is_active.is_(True)
        )

    result = await session.execute(statement)

    return list(result.scalars().all())


@router.patch(
    "/{channel_id}/deactivate",
    response_model=ChannelResponse,
)
async def deactivate_channel(
    channel_id: Annotated[int, Path(ge=1)],
    _user: ChannelManager,
    session: DatabaseSession,
) -> Channel:
    """Deactivate a registered channel."""

    channel = await session.get(
        Channel,
        channel_id,
    )

    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )

    channel.is_active = False

    await session.commit()
    await session.refresh(channel)

    return channel


@router.patch(
    "/{channel_id}/reactivate",
    response_model=ChannelResponse,
)
async def reactivate_channel(
    channel_id: Annotated[int, Path(ge=1)],
    _user: ChannelManager,
    session: DatabaseSession,
) -> Channel:
    """Reactivate a registered channel."""

    channel = await session.get(
        Channel,
        channel_id,
    )

    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )

    channel.is_active = True

    await session.commit()
    await session.refresh(channel)

    return channel
