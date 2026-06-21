import uuid

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.models.types import GUID, uuid_pk

# One row per user. A missing row means defaults (all alert types on, 3-day
# lead): detection treats absence as DEFAULT_PREFERENCE.

DEFAULT_LEAD_TIME_DAYS = 3


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid_pk)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    renewals_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trial_conversions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missed_payments_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_LEAD_TIME_DAYS, nullable=False
    )
