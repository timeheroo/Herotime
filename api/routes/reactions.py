
"""Reaction configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import Channel, ReactionConfig

router = APIRouter(prefix="/reactions", tags=["Reactions"])


class ReactionCreate(BaseModel):
    channel_id: int = Field(gt=0)
    emoji: str = Field(min_length=1, max_length=32)
    configured_quantity: int = Field(default=0, ge=0, le=100000)
    is_enabled: bool = False


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


@router.post("", response_model=ReactionResponse, status_code=201)
async def create_reaction_config(
    payload: ReactionCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a reaction preference for a registered channel."""
    channel = await session.get(Channel, payload.channel_id)

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    if not channel.is_active and payload.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Reactivate the channel before enabling its configuration.",
        )

    config = ReactionConfig(
        channel_id=payload.channel_id,
        emoji=payload.emoji.strip(),
        configured_quantity=payload.configured_quantity,
        is_enabled=payload.is_enabled,
    )

    if not config.emoji:
        raise HTTPException(status_code=422, detail="Emoji cannot be empty.")

    session.add(config)

    try:
        await session.commit()
        await session.refresh(config)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A configuration for this channel and emoji already exists.",
        )

    return config


@router.get("", response_model=list[ReactionResponse])
async def list_reaction_configs(
    channel_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List saved reaction configurations."""
    statement = select(ReactionConfig).order_by(ReactionConfig.id.desc())

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
    session: AsyncSession = Depends(get_session),
):
    """Update a saved configuration; this does not send reactions."""
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

    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
async def delete_reaction_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),
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
