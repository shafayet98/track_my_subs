"""Dashboard + subscription read endpoints.

Thin routers over `services/dashboard.py`, which does the aggregation (monthly
spend, this-vs-last month, per-card totals/overdue). All access is tenant-scoped.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Subscription, User
from app.schemas.dashboard import DashboardSummary, SubscriptionCard, SubscriptionDetail
from app.services import dashboard as dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> DashboardSummary:
    return await dashboard_service.get_summary(db, user.id)


@router.get("/subscriptions", response_model=list[SubscriptionCard])
async def list_subscriptions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SubscriptionCard]:
    return await dashboard_service.get_subscription_cards(db, user.id)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionDetail)
async def get_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetail:
    sub = await db.get(Subscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return await dashboard_service.get_subscription_detail(db, sub)
