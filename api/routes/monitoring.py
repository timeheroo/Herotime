
"""Channel monitoring session API."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import Channel, MonitoringSession

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


class SessionCreate(BaseModel):
    channel_id: int = Field(gt=0)
    configured_target: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class SessionResponse(BaseModel):
    id: int
    channel_id: int
    status: str
    configured_target: int | None
    started_at: datetime | None
    stopped_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a stopped monitoring session."""
    channel = await session.get(Channel, payload.channel_id)

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

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


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    channel_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List monitoring sessions, optionally filtered by channel."""
    statement = select(MonitoringSession).order_by(
        MonitoringSession.id.desc()
    )

    if channel_id is not None:
        statement = statement.where(
            MonitoringSession.channel_id == channel_id
        )

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.patch("/sessions/{session_id}/start", response_model=SessionResponse)
async def start_session(
    session_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Mark a monitoring session as started."""
    item = await session.get(MonitoringSession, session_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    channel = await session.get(Channel, item.channel_id)
    if channel is None or not channel.is_active:
        raise HTTPException(
            status_code=400,
            detail="The channel must exist and be active.",
        )

    if item.status == "running":
        raise HTTPException(
            status_code=409,
            detail="Session is already running.",
        )

    item.status = "running"
    item.started_at = datetime.now(timezone.utc)
    item.stopped_at = None

    await session.commit()
    await session.refresh(item)
    return item


@router.patch("/sessions/{session_id}/stop", response_model=SessionResponse)
async def stop_session(
    session_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Mark a monitoring session as stopped."""
    item = await session.get(MonitoringSession, session_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    if item.status != "running":
        raise HTTPException(
            status_code=409,
            detail="Session is not running.",
        )

    item.status = "stopped"
    item.stopped_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(item)
    return item
