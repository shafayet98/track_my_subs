"""Email-account connection endpoints.

The Gmail OAuth flow and scanning are added in a later PR (see the gmail-sync
skill). For now, listing connected accounts works; the OAuth endpoints are
explicit 501 stubs so the API shape is visible.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import EmailAccount, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


class EmailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    email_address: str


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[EmailAccount]:
    rows = await db.scalars(select(EmailAccount).where(EmailAccount.user_id == user.id))
    return list(rows)


@router.get("/gmail/connect", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def gmail_connect(user: User = Depends(get_current_user)) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail OAuth connect not implemented yet (see gmail-sync skill).",
    )


@router.get("/gmail/callback", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def gmail_callback() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail OAuth callback not implemented yet (see gmail-sync skill).",
    )
