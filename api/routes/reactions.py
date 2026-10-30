
"""Authenticated reaction configuration API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DatabaseSession, require_permission
from database.models import Channel, ReactionConfig, User


router = APIRouter(
    prefix="/reactions",
    tags=["Reactions"],
)


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
        default=None,
        ge=0,
        le=100000,
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
) -> ReactionConfig:
    """Save a reaction preference for a registered channel."""

    channel = await session.get(Channel, payload.channel_id)

    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )

    if not channel.is_active and payload.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A configuration for this channel and emoji "
                "already exists."
            ),
        ) from exc

    return config


@router.get(
    "",
    response_model=list[ReactionResponse],
)
async def list_reaction_configs(
    _user: ReactionManager,
    session: DatabaseSession,
    channel_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[ReactionConfig]:
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


@router.patch(
    "/{config_id}",
    response_model=ReactionResponse,
)
async def update_reaction_config(
    config_id: Annotated[int, Path(ge=1)],
    payload: ReactionUpdate,
    _user: ReactionManager,
    session: DatabaseSession,
) -> ReactionConfig:
    """Update configuration only; this does not send reactions."""

    config = await session.get(
        ReactionConfig,
        config_id,
    )

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reaction configuration not found.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if "configured_quantity" in changes:
        if changes["configured_quantity"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Configured quantity cannot be null.",
            )

        config.configured_quantity = changes["configured_quantity"]

    if "is_enabled" in changes:
        if changes["is_enabled"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Enabled status cannot be null.",
            )

        if changes["is_enabled"]:
            channel = await session.get(
                Channel,
                config.channel_id,
            )

            if channel is None or not channel.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "The channel must exist and be active "
                        "before enabling its configuration."
                    ),
                )

        config.is_enabled = changes["is_enabled"]

    await session.commit()
    await session.refresh(config)

    return config


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reaction_config(
    config_id: Annotated[int, Path(ge=1)],
    _user: ReactionManager,
    session: DatabaseSession,
) -> None:
    """Delete a saved reaction preference."""

    config = await session.get(
        ReactionConfig,
        config_id,
    )

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reaction configuration not found.",
        )

    await session.delete(config)
    await session.commit()
