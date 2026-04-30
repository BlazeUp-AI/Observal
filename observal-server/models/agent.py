import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class AgentStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    active = "active"
    rejected = "rejected"
    archived = "archived"


class AgentVisibility(str, enum.Enum):
    public = "public"
    private = "private"


class AgentTeamAccess(Base):
    __tablename__ = "agent_team_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(50), nullable=False)  # 'view', 'edit'

    agent: Mapped["Agent"] = relationship(back_populates="team_accesses")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("name", "created_by", name="uq_agents_name_created_by"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    external_mcps: Mapped[list] = mapped_column(JSON, default=list)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    required_ide_features: Mapped[list] = mapped_column(JSON, default=list)
    inferred_supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    visibility: Mapped[AgentVisibility] = mapped_column(Enum(AgentVisibility), default=AgentVisibility.private)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_users: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    components: Mapped[list["AgentComponent"]] = relationship(
        back_populates="agent", lazy="selectin", order_by="AgentComponent.order_index", cascade="all, delete-orphan"
    )
    goal_template: Mapped["AgentGoalTemplate | None"] = relationship(
        back_populates="agent", lazy="selectin", uselist=False, cascade="all, delete-orphan"
    )
    team_accesses: Mapped[list["AgentTeamAccess"]] = relationship(
        back_populates="agent", lazy="selectin", cascade="all, delete-orphan"
    )


class AgentGoalTemplate(Base):
    __tablename__ = "agent_goal_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="goal_template")
    sections: Mapped[list["AgentGoalSection"]] = relationship(
        back_populates="goal_template", lazy="selectin", order_by="AgentGoalSection.order", cascade="all, delete-orphan"
    )


class AgentGoalSection(Base):
    __tablename__ = "agent_goal_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_goal_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grounding_required: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    goal_template: Mapped["AgentGoalTemplate"] = relationship(back_populates="sections")


from models.agent_component import AgentComponent  # noqa: E402

AgentComponent.agent = relationship("Agent", back_populates="components")
