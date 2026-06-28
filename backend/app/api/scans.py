"""Scan endpoints.

Starting a scan creates a `scan_run` and runs the agent as a background job
(see the agent-tooling skill). Reading a scan run reports its status.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_scan_job
from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import EmailAccount, ScanRun, User

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    emails_scanned: int
    subscriptions_found: int
    summary: str | None = None


@router.post("", response_model=ScanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScanRun:
    accounts = (await db.scalars(select(EmailAccount).where(EmailAccount.user_id == user.id))).all()
    has_credential = any(
        a.app_password_encrypted or a.oauth_refresh_token_encrypted for a in accounts
    )
    if not has_credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect an email account before scanning.",
        )

    scan = ScanRun(user_id=user.id, status="running", started_at=datetime.now(UTC))
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    background_tasks.add_task(run_scan_job, scan.id, user.id)
    return scan


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
