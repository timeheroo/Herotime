
"""Admin and feature-permission management API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import AdminPermission, User

router = APIRouter(prefix="/admin", tags=["Admin"])


class PermissionCreate(BaseModel):
    user_id: int = Field(gt=0)
    permission: str = Field(min_length=1, max_length=100)
    is_enabled: bool = True


class PermissionUpdate(BaseModel):
    is_enabled: bool


class PermissionResponse(BaseModel):
    id: int
    user_id: int
    permission: str
    is_enabled: bool

    model_config = {"from_attributes": True}


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    user_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List stored permissions, optionally for one user."""
    statement = select(AdminPermission).order_by(AdminPermission.id.desc())

    if user_id is not None:
        statement = statement.where(AdminPermission.user_id == user_id)

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=201,
)
async def create_permission(
    payload: PermissionCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a permission entry for an existing user."""
    user = await session.get(User, payload.user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    permission_name = payload.permission.strip()

    if not permission_name:
        raise HTTPException(
            status_code=422,
            detail="Permission name cannot be empty.",
        )

    item = AdminPermission(
        user_id=payload.user_id,
        permission=permission_name,
        is_enabled=payload.is_enabled,
    )
    session.add(item)

    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This user already has a record for that permission.",
        )

    return item


@router.patch(
    "/permissions/{permission_id}",
    response_model=PermissionResponse,
)
async def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Enable or disable a stored permission."""
    item = await session.get(AdminPermission, permission_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Permission not found.")

    item.is_enabled = payload.is_enabled
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/permissions/{permission_id}", status_code=204)
async def delete_permission(
    permission_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a permission entry."""
    item = await session.get(AdminPermission, permission_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Permission not found.")

    await session.delete(item)
    await session.commit()
