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
"""Request schema for registering Telegram account metadata."""

```
label: str = Field(min_length=1, max_length=255)
telegram_user_id: int | None = None
username: str | None = Field(default=None, max_length=255)
```

class AccountResponse(BaseModel):
"""Public account information; never expose session credentials."""

```
model_config = ConfigDict(from_attributes=True)

id: int
label: str
telegram_user_id: int | None
username: str | None
status: str
is_active: bool
```

@router.get("", response_model=list[AccountResponse])
async def list_accounts(
session: DatabaseSession,
user: Annotated[User, Depends(get_authenticated_user)],
) -> list[TelegramAccount]:
"""List registered Telegram accounts without exposing secrets."""

```
result = await session.execute(
    select(TelegramAccount).order_by(TelegramAccount.id.desc())
)
return list(result.scalars().all())
```

@router.post(
"",
response_model=AccountResponse,
status_code=status.HTTP_201_CREATED,
)
async def create_account(
payload: AccountCreate,
session: DatabaseSession,
user: Annotated[User, Depends(require_permission("accounts.manage"))],
) -> TelegramAccount:
"""Register account metadata without accepting session secrets."""

```
account = TelegramAccount(
    label=payload.label.strip(),
    telegram_user_id=payload.telegram_user_id,
    username=payload.username.strip() if payload.username else None,
    status="pending",
    is_active=True,
)

session.add(account)

try:
    await session.commit()
    await session.refresh(accoun
```
