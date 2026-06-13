"""Scan endpoints.

Starting a scan invokes the agent (added in a later PR). Listing/reading scan
runs works against the DB now so the API shape is usable.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import ScanRun, User

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    emails_scanned: int
    subscriptions_found: int
    summary: str | None = None


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def start_scan(user: User = Depends(get_current_user)) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Agentic scan not implemented yet (see agent-tooling skill).",
    )


@router.get("/{scan_id}", response_model=ScanRunOut)
async def get_scan(
    scan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScanRun:
    scan = await db.get(ScanRun, scan_id)
    if scan is None or scan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan
