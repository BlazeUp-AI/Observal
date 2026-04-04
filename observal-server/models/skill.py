import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class SkillListing(Base):
    __tablename__ = "skill_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    skill_path: Mapped[str] = mapped_column(String(500), default="/")
    target_agents: Mapped[list] = mapped_column(JSON, default=list)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    triggers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    slash_command: Mapped[str | None] = mapped_column(String(100), nullable=True)
    has_scripts: Mapped[bool] = mapped_column(Boolean, default=False)
    has_templates: Mapped[bool] = mapped_column(Boolean, default=False)
    is_power: Mapped[bool] = mapped_column(Boolean, default=False)
    power_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcp_server_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    activation_keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SkillDownload(Base):
    __tablename__ = "skill_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AgentSkillLink(Base):
    __tablename__ = "agent_skill_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_listings.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
