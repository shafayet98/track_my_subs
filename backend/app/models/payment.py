import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.types import GUID, uuid_pk

# status: "paid" | "upcoming" | "missing" | "overdue"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid_pk)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="paid", nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    # Provenance only — the Gmail message id, never the email body.
    source_message_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    subscription: Mapped["Subscription"] = relationship(back_populates="payments")  # noqa: F821
