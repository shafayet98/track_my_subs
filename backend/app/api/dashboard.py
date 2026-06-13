"""Dashboard + subscription read endpoints.

Aggregation logic (monthly spend, this-vs-last month, per-card totals) lands in
services/dashboard.py in a later PR. Subscription listing works now.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Subscription, User

router = APIRouter(tags=["dashboard"])


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_name: str
    category: str | None = None
    billing_cycle: str
    amount: float | None = None
    currency: str | None = None
    status: str
    next_payment_date: str | None = None


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def list_subscriptions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Subscription]:
    rows = await db.scalars(select(Subscription).where(Subscription.user_id == user.id))
    return list(rows)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
async def get_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    sub = await db.get(Subscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.get("/dashboard/summary", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def dashboard_summary(user: User = Depends(get_current_user)) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Dashboard aggregation not implemented yet.",
    )
