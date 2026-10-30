
"""Secure admin and feature-permission management API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import (
    DatabaseSession,
    require_owner,
    require_permission,
)
from config import OWNER_ID
from database.models import AdminPermission, User


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


class PermissionCreate(BaseModel):
    user_id: int = Field(gt=0)
    permission: str = Field(min_length=1, max_length=80)
    is_enabled: bool = True

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Permission name cannot be empty.")

        return value


class PermissionUpdate(BaseModel):
    is_enabled: bool


class PermissionResponse(BaseModel):
    id: int
    user_id: int
    permission: str
    is_enabled: bool

    model_config = {"from_attributes": True}


OwnerUser = Annotated[
    User,
    Depends(require_owner),
]

AdminUser = Annotated[
    User,
    Depends(require_permission("admin_permissions")),
]


@router.get(
    "/permissions",
    response_model=list[PermissionResponse],
)
async def list_permissions(
    _user: AdminUser,
    session: DatabaseSession,
    user_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[AdminPermission]:
    """List permissions; requires admin_permissions access."""

    statement = select(AdminPermission).order_by(
        AdminPermission.id.desc()
    )

    if user_id is not None:
        statement = statement.where(
            AdminPermission.user_id == user_id
        )

    result = await session.execute(statement)

    return list(result.scalars().all())


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_permission(
    payload: PermissionCreate,
    _user: OwnerUser,
    session: DatabaseSession,
) -> AdminPermission:
    """Only the owner can create permission records."""

    user = await session.get(
        User,
        payload.user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.telegram_id == OWNER_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Do not assign feature permissions to the owner.",
        )

    item = AdminPermission(
        user_id=user.id,
        permission=payload.permission,
        is_enabled=payload.is_enabled,
    )

    session.add(item)

    try:
        await session.commit()
        await session.refresh(item)

    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user already has a record for that permission.",
        ) from exc

    return item


@router.patch(
    "/permissions/{permission_id}",
    response_model=PermissionResponse,
)
async def update_permission(
    permission_id: Annotated[int, Path(ge=1)],
    payload: PermissionUpdate,
    _user: OwnerUser,
    session: DatabaseSession,
) -> AdminPermission:
    """Only the owner can change feature permissions."""

    item = await session.get(
        AdminPermission,
        permission_id,
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found.",
        )

    target_user = await session.get(
        User,
        item.user_id,
    )

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission target user not found.",
        )

    if target_user.telegram_id == OWNER_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner permissions cannot be modified here.",
        )

    item.is_enabled = payload.is_enabled

    await session.commit()
    await session.refresh(item)

    return item


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_permission(
    permission_id: Annotated[int, Path(ge=1)],
    _user: OwnerUser,
    session: DatabaseSession,
) -> None:
    """Only the owner can delete feature permissions."""

    item = await session.get(
        AdminPermission,
        permission_id,
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found.",
        )

    target_user = await session.get(
        User,
        item.user_id,
    )

    if target_user is not None and target_user.telegram_id == OWNER_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner permissions cannot be deleted here.",
        )

    await session.delete(item)
    await session.commit()
