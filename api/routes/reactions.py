
"""API endpoints for reaction configuration management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import (
    DatabaseSession,
    get_authenticated_user,
    require_permission,
)
from database.models import ReactionConfig, User


router = APIRouter(prefix="/reactions", tags=["Reactions"])


class ReactionConfigCreate(BaseModel):
    channel_id: int = Field(gt=0)
    enabled: bool = False
    emoji: str = Field(default="👍", min_length=1, max_length=32)


class ReactionConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    enabled: bool
    emoji: str


@router.get("", response_model=list[ReactionConfigResponse])
async def list_reaction_configs(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """Return saved reaction configurations."""
    result = await session.execute(
        select(ReactionConfig).order_by(ReactionConfig.id.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=ReactionConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reaction_config(
    payload: ReactionConfigCreate,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("reactions.manage"))],
):
    """Save a configuration without performing reactions."""
    config = ReactionConfig(
        channel_id=payload.channel_id,
        enabled=payload.enabled,
        emoji=payload.emoji,
    )

    session.add(config)

    try:
        await session.commit()
        await session.refresh(config)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save this reaction configuration.",
        )

    return config


@router.patch("/{config_id}/disable", status_code=status.HTTP_200_OK)
async def disable_reaction_config(
    config_id: int,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("reactions.manage"))],
):
    """Disable a saved configuration."""
    result = await session.execute(
        select(ReactionConfig).where(ReactionConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reaction configuration not found.",
        )

    config.enabled = False
    await session.commit()

    return {
        "success": True,
        "message": "Reaction configuration disabled.",
        "config_id": config.id,
    }
