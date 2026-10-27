
"""Telegram account metadata management API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import TelegramAccount

router = APIRouter(prefix="/accounts", tags=["Accounts"])


class AccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    username: str | None = Field(default=None, max_length=255)
    secret_reference: str | None = Field(
        default=None,
        max_length=500,
        description="Reference to a securely stored session; never send session secrets here.",
    )


class AccountRename(BaseModel):
    label: str = Field(min_length=1, max_length=100)


class AccountResponse(BaseModel):
    id: int
    label: str
    telegram_user_id: int | None
    username: str | None
    status: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=AccountResponse, status_code=201)
async def add_account(
    payload: AccountCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register account metadata, not a Telegram login session."""
    label = payload.label.strip()
    username = payload.username.strip().lstrip("@") if payload.username else None
    secret_reference = (
        payload.secret_reference.strip()
        if payload.secret_reference
        else None
    )

    if not label:
        raise HTTPException(status_code=422, detail="Label cannot be empty.")

    account = TelegramAccount(
        label=label,
        username=username,
        secret_reference=secret_reference,
        status="pending",
        is_active=True,
    )
    session.add(account)

    try:
        await session.commit()
        await session.refresh(account)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account conflicts with an existing record.",
        )

    return account


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
):
    """List account metadata without exposing secret references."""
    statement = select(TelegramAccount).order_by(TelegramAccount.id.desc())

    if active_only:
        statement = statement.where(TelegramAccount.is_active.is_(True))

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.patch("/{account_id}/rename", response_model=AccountResponse)
async def rename_account(
    account_id: int,
    payload: AccountRename,
    session: AsyncSession = Depends(get_session),
):
    """Change the display label for an account."""
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label cannot be empty.")

    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    account.label = label
    await session.commit()
    await session.refresh(account)
    return account


@router.patch("/{account_id}/deactivate", response_model=AccountResponse)
async def deactivate_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Deactivate account metadata without deleting its record."""
    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    account.is_active = False
    await session.commit()
    await session.refresh(account)
    return account
