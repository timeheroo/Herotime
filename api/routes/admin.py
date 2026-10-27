
"""Owner-only API endpoints for administrator permissions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.dependencies import DatabaseSession, require_owner
from database.models import AdminPermission, User


router = APIRouter(prefix="/admin", tags=["Admin"])


class PermissionUpdate(BaseModel):
    user_id: int = Field(gt=0)
    permission: str = Field(min_length=1, max_length=100)
    enabled: bool


@router.get("/permissions")
async def list_admin_permissions(
    session: DatabaseSession,
    owner: Annotated[User, Depends(require_owner)],
):
    """List configured administrator permissions."""
    result = await session.execute(
        select(AdminPermission).order_by(AdminPermission.id.desc())
    )
    permissions = result.scalars().all()

    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "permission": item.permission,
            "enabled": item.enabled,
        }
        for item in permissions
    ]


@router.put("/permissions")
async def update_admin_permission(
    payload: PermissionUpdate,
    session: DatabaseSession,
    owner: Annotated[User, Depends(require_owner)],
):
    """Create or update a permission for an existing user."""
    target_result = await session.execute(
        select(User).where(User.id == payload.user_id)
    )
    target_user = target_result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if target_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permissions can only be assigned to admin users.",
        )

    result = await session.execute(
        select(AdminPermission).where(
            AdminPermission.user_id == payload.user_id,
            AdminPermission.permission == payload.permission,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = AdminPermission(
            user_id=payload.user_id,
            permission=payload.permission,
            enabled=payload.enabled,
        )
        session.add(record)
    else:
        record.enabled = payload.enabled

    await session.commit()
    await session.refresh(record)

    return {
        "success": True,
        "user_id": record.user_id,
        "permission": record.permission,
        "enabled": record.enabled,
    }
