import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ListingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class McpListing(Base):
    __tablename__ = "mcp_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    setup_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    custom_fields: Mapped[list["McpCustomField"]] = relationship(
        back_populates="listing", lazy="selectin", cascade="all, delete-orphan"
    )
    validation_results: Mapped[list["McpValidationResult"]] = relationship(
        back_populates="listing", lazy="selectin", cascade="all, delete-orphan"
    )


class McpCustomField(Base):
    __tablename__ = "mcp_custom_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mcp_listings.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)

    listing: Mapped["McpListing"] = relationship(back_populates="custom_fields")


class McpDownload(Base):
    __tablename__ = "mcp_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mcp_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class McpValidationResult(Base):
    __tablename__ = "mcp_validation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mcp_listings.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    listing: Mapped["McpListing"] = relationship(back_populates="validation_results")
