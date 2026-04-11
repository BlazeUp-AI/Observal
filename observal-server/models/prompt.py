import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class PromptListing(Base):
    __tablename__ = "prompt_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    model_hints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class PromptDownload(Base):
    __tablename__ = "prompt_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
