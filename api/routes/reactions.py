
"""Authenticated reaction configuration API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DatabaseSession, require_permission
from database.models import Channel, ReactionConfig, User

router = APIRouter(prefix="/reactions", tags=["Reactions"])

ReactionManager = Annotated[
    User,
    Depends(require_permission("reaction_management")),
]


class ReactionCreate(BaseModel):
    channel_id: int = Field(gt=0)
    emoji: str = Field(min_length=1, max_length=32)
    configured_quantity: int = Field(default=0, ge=0, le=100000)
    is_enabled: bool = False

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Emoji cannot be empty.")
        return value


class ReactionUpdate(BaseModel):
    configured_quantity: int | None = Field(
        default=None, ge=0, le=100000
    )
    is_enabled: bool | None = None


class ReactionResponse(BaseModel):
    id: int
    channel_id: int
    emoji: str
    configured_quantity: int
    is_enabled: bool

    model_config = {"from_attributes": True}


@router.post(
    "",
    response_model=ReactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reaction_config(
    payload: ReactionCreate,
    _user: ReactionManager,
    session: DatabaseSession,
):
    """Save a reaction preference for a registered channel."""
    channel = await session.get(Channel, payload.channel_id)

    if channel is None:
        raise HTTPException(
            status_code=404,
            detail="Channel not found.",
        )

    if not channel.is_active and payload.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Reactivate the channel before enabling its configuration.",
        )

    config = ReactionConfig(
        channel_id=payload.channel_id,
        emoji=payload.emoji,
        configured_quantity=payload.configured_quantity,
        is_enabled=payload.is_enabled,
    )
    session.add(config)

    try:
        await session.commit()
        await session.refresh(config)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A configuration for this channel and emoji already exists.",
        ) from exc

    return config


@router.get("", response_model=list[ReactionResponse])
async def list_reaction_configs(
    _user: ReactionManager,
    channel_id: int | None = None,
    session: DatabaseSession = Depends(
        __import__("api.dependencies", fromlist=["get_db_session"]).get_db_session
    ),
):
    """List saved reaction configurations."""
    statement = select(ReactionConfig).order_by(
        ReactionConfig.id.desc()
    )

    if channel_id is not None:
        statement = statement.where(
            ReactionConfig.channel_id == channel_id
        )

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.patch("/{config_id}", response_model=ReactionResponse)
async def update_reaction_config(
    config_id: int,
    payload: ReactionUpdate,
    _user: ReactionManager,
    session: DatabaseSession,
):
    """Update configuration only; this does not send reactions."""
    config = await session.get(ReactionConfig, config_id)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Reaction configuration not found.",
        )

    changes = payload.model_fields_set

    if "configured_quantity" in changes:
        config.configured_quantity = payload.configured_quantity

    if "is_enabled" in changes:
        config.is_enabled = payload.is_enabled

    channel = await session.get(Channel, config.channel_id)
    if channel is not None and not channel.is_active and config.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Reactivate the channel before enabling its configuration.",
        )

    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reaction_config(
    config_id: int,
    _user: ReactionManager,
    session: DatabaseSession,
):
    """Delete a saved reaction preference."""
    config = await session.get(ReactionConfig, config_id)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Reaction configuration not found.",
        )

    await session.delete(config)
    await session.commit()
