import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.types import GUID, uuid_pk

# String-valued enums (kept as plain strings for portability):
#   billing_cycle: "monthly" | "annual" | "weekly" | "quarterly" | "unknown"
#   status:        "active" | "cancelled" | "unknown"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid_pk)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    billing_cycle: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    next_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Date a free trial converts to a paid plan (the convert-to amount is `amount`).
    trial_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        back_populates="subscription", cascade="all, delete-orphan"
    )
