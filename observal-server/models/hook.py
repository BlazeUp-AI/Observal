import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.mcp import ListingStatus


class HookListing(Base):
    __tablename__ = "hook_listings"
    __table_args__ = (
        Index("ix_hook_listings_status", "status"),
        Index("ix_hook_listings_submitted_by", "submitted_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    bundle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("component_bundles.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(10), default="async")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    handler_type: Mapped[str] = mapped_column(String(20), nullable=False)
    handler_config: Mapped[dict] = mapped_column(JSON, default=dict)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="agent")
    tool_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_pattern: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latest_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hook_versions.id", use_alter=True, ondelete="SET NULL"),
        nullable=True,
    )

    versions: Mapped[list["HookVersion"]] = relationship(
        back_populates="listing",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="HookVersion.listing_id",
    )


class HookDownload(Base):
    __tablename__ = "hook_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hook_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class HookVersion(Base):
    __tablename__ = "hook_versions"
    __table_args__ = (
        UniqueConstraint("listing_id", "version"),
        Index("ix_hook_versions_listing_id", "listing_id"),
        Index("ix_hook_versions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hook_listings.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    released_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(10), default="async")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    handler_type: Mapped[str] = mapped_column(String(20), nullable=False)
    handler_config: Mapped[dict] = mapped_column(JSON, default=dict)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="agent")
    tool_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_pattern: Mapped[list | None] = mapped_column(JSON, nullable=True)

    listing: Mapped["HookListing"] = relationship(back_populates="versions", foreign_keys=[listing_id])
