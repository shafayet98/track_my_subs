"""Notification-preference endpoints.

Thin router over `services/notifications.py`. Each user has at most one
preference row; a missing row reads as defaults. All access is tenant-scoped.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import User
from app.schemas.notifications import (
    NotificationPreferenceOut,
    NotificationPreferenceUpdate,
)
from app.services import notifications as notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferenceOut)
async def get_preferences(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> NotificationPreferenceOut:
    pref = await notifications_service.get_preferences(db, user.id)
    return NotificationPreferenceOut.model_validate(pref)


@router.put("/preferences", response_model=NotificationPreferenceOut)
async def update_preferences(
    body: NotificationPreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferenceOut:
    pref = await notifications_service.update_preferences(
        db, user.id, **body.model_dump(exclude_none=True)
    )
    return NotificationPreferenceOut.model_validate(pref)
