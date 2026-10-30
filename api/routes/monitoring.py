
"""Authenticated channel monitoring session API."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from api.dependencies import DatabaseSession, require_permission
from database.models import Channel, MonitoringSession, User


router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
)


MonitoringManager = Annotated[
    User,
    Depends(require_permission("monitoring_management")),
]


class SessionCreate(BaseModel):
    channel_id: int = Field(gt=0)
    configured_target: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class SessionResponse(BaseModel):
    id: int
    channel_id: int
    status: str
    configured_target: int | None
    started_at: datetime | None
    stopped_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: SessionCreate,
    _user: MonitoringManager,
    session: DatabaseSession,
) -> MonitoringSession:
    """Create a stopped monitoring session."""

    channel = await session.get(
        Channel,
        payload.channel_id,
    )

    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )

    if not channel.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The channel must be active.",
        )

    item = MonitoringSession(
        channel_id=payload.channel_id,
        status="stopped",
        configured_target=payload.configured_target,
        notes=payload.notes,
    )

    session.add(item)

    await session.commit()
    await session.refresh(item)

    return item


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
)
async def list_sessions(
    _user: MonitoringManager,
    session: DatabaseSession,
    channel_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[MonitoringSession]:
    """List monitoring sessions."""

    statement = select(MonitoringSession).order_by(
        MonitoringSession.id.desc()
    )

    if channel_id is not None:
        statement = statement.where(
            MonitoringSession.channel_id == channel_id
        )

    result = await session.execute(statement)

    return list(result.scalars().all())


@router.patch(
    "/sessions/{session_id}/start",
    response_model=SessionResponse,
)
async def start_session(
    session_id: Annotated[int, Path(ge=1)],
    _user: MonitoringManager,
    session: DatabaseSession,
) -> MonitoringSession:
    """Mark a monitoring session as running."""

    item = await session.get(
        MonitoringSession,
        session_id,
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    if item.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already running.",
        )

    channel = await session.get(
        Channel,
        item.channel_id,
    )

    if channel is None or not channel.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The channel must exist and be active.",
        )

    item.status = "running"
    item.started_at = datetime.now(timezone.utc)
    item.stopped_at = None

    await session.commit()
    await session.refresh(item)

    return item


@router.patch(
    "/sessions/{session_id}/stop",
    response_model=SessionResponse,
)
async def stop_session(
    session_id: Annotated[int, Path(ge=1)],
    _user: MonitoringManager,
    session: DatabaseSession,
) -> MonitoringSession:
    """Mark a monitoring session as stopped."""

    item = await session.get(
        MonitoringSession,
        session_id,
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    if item.status != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not running.",
        )

    item.status = "stopped"
    item.stopped_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(item)

    return item
