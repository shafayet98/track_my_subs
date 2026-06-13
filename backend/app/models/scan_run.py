import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.models.types import GUID, uuid_pk

# status: "running" | "succeeded" | "failed"


class ScanRun(Base, TimestampMixin):
    __tablename__ = "scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid_pk)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    emails_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subscriptions_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
