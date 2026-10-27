
"""API endpoints for monitoring session status."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from api.dependencies import (
    DatabaseSession,
    get_authenticated_user,
    require_permission,
)
from database.models import MonitoringSession, User


router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


class MonitoringSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None


@router.get("/sessions", response_model=list[MonitoringSessionResponse])
async def list_monitoring_sessions(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """List saved monitoring sessions."""
    result = await session.execute(
        select(MonitoringSession)
        .order_by(MonitoringSession.id.desc())
        .limit(200)
    )
    return result.scalars().all()


@router.patch("/sessions/{session_id}/stop")
async def stop_monitoring_session(
    session_id: int,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("monitoring.manage"))],
):
    """Mark a monitoring session as stopped."""
    result = await session.execute(
        select(MonitoringSession).where(
            MonitoringSession.id == session_id
        )
    )
    monitoring_session = result.scalar_one_or_none()

    if monitoring_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoring session not found.",
        )

    monitoring_session.status = "stopped"
    monitoring_session.ended_at = datetime.utcnow()

    await session.commit()

    return {
        "success": True,
        "message": "Monitoring session marked as stopped.",
        "session_id": monitoring_session.id,
    }
