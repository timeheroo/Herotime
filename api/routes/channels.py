"""API endpoints for channel management."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
telegram_chat_id: int | None = None
title: str = Field(min_length=1, max_length=255)
username: str | None = Field(default=None, max_length=255)
chat_link: str | None = Field(default=None, max_length=512)
chat_type: Literal["channel", "group", "supergroup"] = "channel"

class ChannelResponse(BaseModel):
model_config = ConfigDict(from_attributes=True)

```
id: int
telegram_chat_id: int | None
username: str | None
title: str
chat_link: str | None
chat_type: str
is_active: bool
```

@router.get("", response_model=list[ChannelResponse])
async def list_channels(
session: DatabaseSession,
user: Annotated[User, Depends(get_authenticated_user)],
include_inactive: bool = Query(default=False),
):
"""List channels; optionally include deactivated channels."""
query = select(Channel).order_by(Channel.id.desc())

```
if not include_inactive:
    query = query.where(Channel.is_active.is_(True))

result = await session.execute(query)
return result.scalars().all()
```

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
"""Register a channel record."""
username = payload.username.strip().lstrip("@") if payload.username else None
chat_link = payload.chat_link.strip() if payload.chat_link else None
title = payload.title.strip()

```
if not title:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Channel title cannot be empty.",
    )

if payload.telegram_chat_id is None and not username and not chat_link:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Provide telegram_chat_id, username, or chat_link.",
    )

if payload.telegram_chat_id is not None:
    result = await session.execute(
        select(Channel).where(
            Channel.telegram_chat_id == payload.telegram_chat_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A channel with this Telegram chat ID already exists.",
        )

channel = Channel(
    telegram_chat_id=payload.telegram_chat_id,
    title=title,
    username=username,
    chat_link=chat_link,
    chat_type=payload.chat_type,
    created_by_user_id=user.id,
    is_active=True,
)

session.add(channel)

try:
    await session.commit()
    await session.refresh(channel)
except IntegrityError as exc:
    await session.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A conflicting channel record already exists.",
    ) from exc

return channel
```

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

```
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
```

@router.patch("/{channel_id}/activate", response_model=ChannelResponse)
async def activate_channel(
channel_id: int,
session: DatabaseSession,
user: Annotated[User, Depends(require_permission("channels.manage"))],
):
"""Reactivate a previously deactivated channel."""
result = await session.execute(
select(Channel).where(Channel.id == channel_id)
)
channel = result.scalar_one_or_none()

```
if channel is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Channel not found.",
    )

channel.is_active = True
await session.commit()
await session.refresh(channel)

return channel
```
