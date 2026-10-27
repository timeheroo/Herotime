"""API endpoints for reaction configuration management."""

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
from database.models import Channel, ReactionConfig, User

router = APIRouter(prefix="/reactions", tags=["Reactions"])

class ReactionConfigCreate(BaseModel):
"""Request schema for creating a reaction configuration."""

```
channel_id: int = Field(gt=0)
emoji: str = Field(default="👍", min_length=1, max_length=32)
configured_quantity: int = Field(default=0, ge=0)
is_enabled: bool = True
```

class ReactionConfigResponse(BaseModel):
"""Public response schema for a reaction configuration."""

```
model_config = ConfigDict(from_attributes=True)

id: int
channel_id: int
emoji: str
configured_quantity: int
is_enabled: bool
```

@router.get("", response_model=list[Reacti
