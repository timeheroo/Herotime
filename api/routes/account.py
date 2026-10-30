
"""Authenticated Telegram account metadata management API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DatabaseSession, require_permission
from database.models import TelegramAccount, User


router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


AccountManager = Annotated[
    User,
    Depends(require_permission("account_management")),
]


class AccountCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    username: str | None = Field(default=None, max_length=255)

    def normalized_label(self) -> str:
        return self.label.strip()

    def normalized_username(self) -> str | None:
        if self.username is None:
            return None

        username = self.username.strip().lstrip("@")
        return username or None


class AccountRename(BaseModel):
    label: str = Field(min_length=1, max_length=100)

    def normalized_label(self) -> str:
        return self.label.strip()


class AccountResponse(BaseModel):
    id: int
    label: str
    telegram_user_id: int | None
    username: str | None
    status: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_account(
    payload: AccountCreate,
    _user: AccountManager,
    session: DatabaseSession,
) -> TelegramAccount:
    """Register account metadata, not a Telegram login session."""

    label = payload.normalized_label()
    username = payload.normalized_username()

    if not label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Label cannot be empty.",
        )

    account = TelegramAccount(
        label=label,
        username=username,
        status="pending",
        is_active=True,
    )

    session.add(account)

    try:
        await session.commit()
        await session.refresh(account)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account conflicts with an existing record.",
        ) from exc

    return account


@router.get(
    "",
    response_model=list[AccountResponse],
)
async def list_accounts(
    _user: AccountManager,
    session: DatabaseSession,
    active_only: bool = True,
) -> list[TelegramAccount]:
    """List account metadata without exposing secret references."""

    statement = select(TelegramAccount).order_by(
        TelegramAccount.id.desc()
    )

    if active_only:
        statement = statement.where(
            TelegramAccount.is_active.is_(True)
        )

    result = await session.execute(statement)

    return list(result.scalars().all())


@router.patch(
    "/{account_id}/rename",
    response_model=AccountResponse,
)
async def rename_account(
    account_id: Annotated[int, Path(ge=1)],
    payload: AccountRename,
    _user: AccountManager,
    session: DatabaseSession,
) -> TelegramAccount:
    """Change the display label for an account."""

    label = payload.normalized_label()

    if not label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Label cannot be empty.",
        )

    account = await session.get(
        TelegramAccount,
        account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    account.label = label

    await session.commit()
    await session.refresh(account)

    return account


@router.patch(
    "/{account_id}/deactivate",
    response_model=AccountResponse,
)
async def deactivate_account(
    account_id: Annotated[int, Path(ge=1)],
    _user: AccountManager,
    session: DatabaseSession,
) -> TelegramAccount:
    """Deactivate account metadata without deleting its record."""

    account = await session.get(
        TelegramAccount,
        account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    account.is_active = False

    await session.commit()
    await session.refresh(account)

    return account
