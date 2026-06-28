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
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import create_oauth_state, encrypt_token, verify_oauth_state
from app.integrations import gmail
from app.integrations.email_imap import ImapClient
from app.models import EmailAccount, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


class EmailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    email_address: str


class ConnectUrlOut(BaseModel):
    authorization_url: str


class ImapConnectIn(BaseModel):
    email_address: EmailStr
    app_password: str = Field(min_length=1)
    imap_host: str | None = None


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


@router.post("/imap/connect", response_model=EmailAccountOut)
async def imap_connect(
    body: ImapConnectIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailAccount:
    """Connect a mailbox via IMAP + App Password (no OAuth).

    Validates the credentials with a real login before storing the app password
    encrypted at rest. See .claude/rules/security.md for the credential trade-off.
    """
    host = (body.imap_host or "").strip() or settings.imap_default_host
    email_address = str(body.email_address)
    client = ImapClient.from_credentials(host, email_address, body.app_password)

    try:
        await run_in_threadpool(client.check_login)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not connect to the mailbox. Check the email, app password, and host.",
        ) from exc

    encrypted = encrypt_token(body.app_password)
    account = await db.scalar(
        select(EmailAccount).where(
            EmailAccount.user_id == user.id,
            EmailAccount.provider == "imap",
            EmailAccount.email_address == email_address,
        )
    )
    if account is None:
        account = EmailAccount(
            user_id=user.id,
            provider="imap",
            email_address=email_address,
            imap_host=host,
            app_password_encrypted=encrypted,
        )
        db.add(account)
    else:
        account.imap_host = host
        account.app_password_encrypted = encrypted
    await db.commit()
    await db.refresh(account)
    return account
