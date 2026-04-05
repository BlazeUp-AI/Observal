import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    metric: Mapped[str] = mapped_column(String(50))  # error_rate | latency_p99 | token_usage
    threshold: Mapped[float] = mapped_column(Float)
    condition: Mapped[str] = mapped_column(String(10))  # above | below
    target_type: Mapped[str] = mapped_column(String(20))  # mcp | agent | all
    target_id: Mapped[str] = mapped_column(String(255), default="")
    webhook_url: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
