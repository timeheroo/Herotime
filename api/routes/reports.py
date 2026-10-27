
"""API endpoints for analytics and reports."""

from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from api.dependencies import DatabaseSession, get_authenticated_user
from database.models import AnalyticsRecord, User


router = APIRouter(prefix="/reports", tags=["Reports"])


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int | None
    metric_name: str
    metric_value: float
    recorded_at: datetime


@router.get("/analytics", response_model=list[AnalyticsResponse])
async def get_analytics(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """Return stored analytics records for the authenticated user."""
    result = await session.execute(
        select(AnalyticsRecord).order_by(AnalyticsRecord.id.desc()).limit(500)
    )
    return result.scalars().all()


@router.get("/summary")
async def get_report_summary(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """Return a basic summary of recorded analytics."""
    result = await session.execute(select(AnalyticsRecord))
    records = result.scalars().all()

    return {
        "records_count": len(records),
        "note": (
            "Summary is based on stored analytics records only. "
            "Missing metrics are not inferred."
        ),
    }
