"""Email-account connection endpoints.

Gmail is connected via Google OAuth2 (read-only). `connect` returns the Google
consent URL; `callback` (hit by the browser, so unauthenticated — the user is
carried in a signed `state`) exchanges the code and stores the **encrypted**
refresh token. Scanning is added in a later PR (see the agent-tooling skill).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import create_oauth_state, encrypt_token, verify_oauth_state
from app.integrations import gmail
from app.models import EmailAccount, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


class EmailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    email_address: str


class ConnectUrlOut(BaseModel):
    authorization_url: str


@router.get("", response_model=list[EmailAccountOut])
async def list_accounts(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[EmailAccount]:
    rows = await db.scalars(select(EmailAccount).where(EmailAccount.user_id == user.id))
    return list(rows)


@router.get("/gmail/connect", response_model=ConnectUrlOut)
async def gmail_connect(user: User = Depends(get_current_user)) -> ConnectUrlOut:
    state = create_oauth_state(str(user.id))
    return ConnectUrlOut(authorization_url=gmail.build_authorization_url(state))


@router.get("/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    subject = verify_oauth_state(state)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state"
        )
    user_id = uuid.UUID(subject)

    result = await run_in_threadpool(gmail.exchange_code, code)

    account = await db.scalar(
        select(EmailAccount).where(
            EmailAccount.user_id == user_id,
            EmailAccount.provider == "gmail",
            EmailAccount.email_address == result.email_address,
        )
    )
    encrypted = encrypt_token(result.refresh_token)
    if account is None:
        db.add(
            EmailAccount(
                user_id=user_id,
                provider="gmail",
                email_address=result.email_address,
                oauth_refresh_token_encrypted=encrypted,
            )
        )
    else:
        account.oauth_refresh_token_encrypted = encrypted
    await db.commit()

    return RedirectResponse(
        url=f"{settings.frontend_origin}/?gmail=connected",
        status_code=status.HTTP_303_SEE_OTHER,
    )
