import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ApiKeyEnvironment(str, enum.Enum):
    """Environment types for API keys."""

    live = "live"
    test = "test"
    dev = "dev"


class ApiKey(Base):
    """API key model supporting multiple keys per user with expiration and rotation."""

    __tablename__ = "api_keys"

    # Primary fields
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA256 hash
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First 10 chars for display
    environment: Mapped[ApiKeyEnvironment] = mapped_column(
        Enum(ApiKeyEnvironment), nullable=False, default=ApiKeyEnvironment.live
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Security tracking
    last_used_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6

    # Future: scope-based permissions (not enforced yet)
    scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    # Table constraints
    __table_args__ = (
        # Unique constraint: user cannot have duplicate key names
        UniqueConstraint("user_id", "name", name="uq_api_keys_user_name"),
        # Check constraint: name must be between 1-100 characters
        CheckConstraint("length(name) >= 1 AND length(name) <= 100", name="ck_api_keys_name_length"),
        # Composite index for fast active key lookup
        Index(
            "idx_api_keys_active_lookup",
            "key_hash",
            "user_id",
            postgresql_where=(revoked_at.is_(None)),
        ),
        # Index for user's keys by environment
        Index("idx_api_keys_user_environment", "user_id", "environment"),
    )

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def is_revoked(self) -> bool:
        """Check if the key has been revoked."""
        return self.revoked_at is not None

    def is_valid(self) -> bool:
        """Check if the key is valid (not expired and not revoked)."""
        return not self.is_expired() and not self.is_revoked()

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name={self.name}, prefix={self.prefix}, environment={self.environment.value})>"
