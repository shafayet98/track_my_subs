"""Schemas for the notification-preferences API."""

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    renewals_enabled: bool
    trial_conversions_enabled: bool
    missed_payments_enabled: bool
    lead_time_days: int


class NotificationPreferenceUpdate(BaseModel):
    """All fields optional — a PUT updates only what's provided."""

    renewals_enabled: bool | None = None
    trial_conversions_enabled: bool | None = None
    missed_payments_enabled: bool | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=30)
