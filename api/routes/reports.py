
"""Authenticated reports and analytics API."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.dependencies import DatabaseSession, require_permission
from database.models import AnalyticsRecord, Channel, User

router = APIRouter(prefix="/reports", tags=["Reports"])

ReportPeriod = Literal["24h", "72h", "1d", "1w", "1m"]

ReportViewer = Annotated[
    User,
    Depends(require_permission("reports_view")),
]

ReportManager = Annotated[
    User,
    Depends(require_permission("reports_manage")),
]


class AnalyticsCreate(BaseModel):
    channel_id: int = Field(gt=0)
    source: str = Field(min_length=1, max_length=100)
    metric_name: str = Field(min_length=1, max_length=100)
    metric_value: int | None = None
    details: dict | None = None


class AnalyticsResponse(BaseModel):
    id: int
    channel_id: int
    source: str
    metric_name: str
    metric_value: int | None
    observed_at: datetime
    details: dict | None

    model_config = {"from_attributes": True}


PERIOD_DAYS = {
    "24h": 1,
    "72h": 3,
    "1d": 1,
    "1w": 7,
    "1m": 30,
}


@router.post(
    "/records",
    response_model=AnalyticsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analytics_record(
    payload: AnalyticsCreate,
    _user: ReportManager,
    session: DatabaseSession,
):
    """Record an observed metric; does not generate synthetic statistics."""
    channel = await session.get(Channel, payload.channel_id)

    if channel is None:
        raise HTTPException(
            status_code=404,
            detail="Channel not found.",
        )

    source = payload.source.strip()
    metric_name = payload.metric_name.strip()

    if not source or not metric_name:
        raise HTTPException(
            status_code=422,
            detail="Source and metric name cannot be empty.",
        )

    record = AnalyticsRecord(
        channel_id=payload.channel_id,
        source=source,
        metric_name=metric_name,
        metric_value=payload.metric_value,
        details=payload.details,
        observed_at=datetime.now(timezone.utc),
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.get("", response_model=list[AnalyticsResponse])
async def get_report(
    _user: ReportViewer,
    channel_id: int | None = Query(default=None, gt=0),
    period: ReportPeriod = "24h",
    limit: int = Query(default=100, ge=1, le=1000),
    session: DatabaseSession = Depends(
        __import__("api.dependencies", fromlist=["get_db_session"]).get_db_session
    ),
):
    """Return recorded metrics within the selected period."""
    since = datetime.now(timezone.utc) - timedelta(
        days=PERIOD_DAYS[period]
    )

    statement = (
        select(AnalyticsRecord)
        .where(AnalyticsRecord.observed_at >= since)
        .order_by(AnalyticsRecord.observed_at.desc())
        .limit(limit)
    )

    if channel_id is not None:
        statement = statement.where(
            AnalyticsRecord.channel_id == channel_id
        )

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.get("/summary")
async def get_report_summary(
    _user: ReportViewer,
    channel_id: int | None = Query(default=None, gt=0),
    period: ReportPeriod = "24h",
    session: DatabaseSession = Depends(
        __import__("api.dependencies", fromlist=["get_db_session"]).get_db_session
    ),
):
    """Summarize recorded numeric values only."""
    since = datetime.now(timezone.utc) - timedelta(
        days=PERIOD_DAYS[period]
    )

    statement = select(AnalyticsRecord).where(
        AnalyticsRecord.observed_at >= since
    )

    if channel_id is not None:
        statement = statement.where(
            AnalyticsRecord.channel_id == channel_id
        )

    result = await session.execute(statement)
    records = list(result.scalars().all())

    totals: dict[str, int] = {}
    for record in records:
        if record.metric_value is not None:
            totals[record.metric_name] = (
                totals.get(record.metric_name, 0)
                + record.metric_value
            )

    return {
        "period": period,
        "record_count": len(records),
        "totals": totals,
        "message": "Summary includes only recorded numeric metric values.",
    }
