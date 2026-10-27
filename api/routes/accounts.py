
"""API endpoints for Telegram account management."""

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
from database.models import TelegramAccount, User


router = APIRouter(prefix="/accounts", tags=["Accounts"])


class AccountCreate(BaseModel):
    telegram_user_id: int
    username: str | None = Field(default=None, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)


class AccountResponse(BaseModel):
    """Public account information; never expose session credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_user_id: int
    username: str | None
    display_name: str
    status: str


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    session: DatabaseSession,
    user: Annotated[User, Depends(get_authenticated_user)],
):
    """List registered Telegram accounts."""
    result = await session.execute(
        select(TelegramAccount).order_by(TelegramAccount.id.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: AccountCreate,
    session: DatabaseSession,
    user: Annotated[User, Depends(require_permission("accounts.manage"))],
):
    """Register account metadata without accepting session secrets."""
    account = TelegramAccount(
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        display_name=payload.display_name.strip(),
        status="pending",
    )

    session.add(account)

    try:
        await session.commit()
        await session.refresh(account)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Telegram account may already be registered.",
        )

    return account
