"""Scoring models for the 5-dimension penalty-based eval system."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ScoringDimension(str, enum.Enum):
    goal_completion = "goal_completion"
    tool_efficiency = "tool_efficiency"
    tool_failures = "tool_failures"
    factual_grounding = "factual_grounding"
    thought_process = "thought_process"


class PenaltySeverity(str, enum.Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"


class PenaltyTriggerType(str, enum.Enum):
    structural = "structural"
    slm_assisted = "slm_assisted"
    absence = "absence"


# Default weights per dimension
DEFAULT_DIMENSION_WEIGHTS: dict[ScoringDimension, float] = {
    ScoringDimension.goal_completion: 0.30,
    ScoringDimension.tool_efficiency: 0.20,
    ScoringDimension.tool_failures: 0.15,
    ScoringDimension.factual_grounding: 0.20,
    ScoringDimension.thought_process: 0.15,
}


class PenaltyDefinition(Base):
    """Catalog of possible penalties that can be applied to traces."""

    __tablename__ = "penalty_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dimension: Mapped[ScoringDimension] = mapped_column(Enum(ScoringDimension), nullable=False)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # negative
    severity: Mapped[PenaltySeverity] = mapped_column(Enum(PenaltySeverity), nullable=False)
    trigger_type: Mapped[PenaltyTriggerType] = mapped_column(Enum(PenaltyTriggerType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class DimensionWeight(Base):
    """Per-agent or global default dimension weights."""

    __tablename__ = "dimension_weights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True
    )
    dimension: Mapped[ScoringDimension] = mapped_column(Enum(ScoringDimension), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)


class TracePenalty(Base):
    """Records each penalty applied to a specific trace scorecard."""

    __tablename__ = "trace_penalties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scorecards.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[ScoringDimension] = mapped_column(Enum(ScoringDimension), nullable=False)
    penalty_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("penalty_definitions.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    trace_event_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scorecard: Mapped["Scorecard"] = relationship(back_populates="penalties")
    penalty_definition: Mapped["PenaltyDefinition"] = relationship(lazy="selectin")


# Default penalty catalog seed data
DEFAULT_PENALTIES: list[dict] = [
    # Goal Completion (weight 0.30)
    {
        "dimension": ScoringDimension.goal_completion,
        "event_name": "missing_required_section",
        "amount": -25,
        "severity": PenaltySeverity.critical,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "A required output section is completely missing from the agent's response.",
    },
    {
        "dimension": ScoringDimension.goal_completion,
        "event_name": "empty_stub_section",
        "amount": -15,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "A section is present but contains only stub/placeholder content.",
    },
    {
        "dimension": ScoringDimension.goal_completion,
        "event_name": "ungrounded_section",
        "amount": -10,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "A section's content is not grounded in tool call results.",
    },
    # Tool Efficiency (weight 0.20)
    {
        "dimension": ScoringDimension.tool_efficiency,
        "event_name": "duplicate_tool_call",
        "amount": -5,
        "severity": PenaltySeverity.minor,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "Same tool called with identical parameters.",
    },
    {
        "dimension": ScoringDimension.tool_efficiency,
        "event_name": "unused_tool_result",
        "amount": -3,
        "severity": PenaltySeverity.minor,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "Tool call output is never referenced in subsequent processing.",
    },
    {
        "dimension": ScoringDimension.tool_efficiency,
        "event_name": "excessive_tool_calls",
        "amount": -10,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "Number of tool calls exceeds 2x the rolling median for this agent.",
    },
    {
        "dimension": ScoringDimension.tool_efficiency,
        "event_name": "zero_tool_calls_when_needed",
        "amount": -20,
        "severity": PenaltySeverity.critical,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "Agent has linked MCPs but trace has zero tool call spans.",
    },
    # Tool Failures (weight 0.15)
    {
        "dimension": ScoringDimension.tool_failures,
        "event_name": "tool_call_error",
        "amount": -10,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "A tool call returned an error status.",
    },
    {
        "dimension": ScoringDimension.tool_failures,
        "event_name": "tool_call_timeout",
        "amount": -8,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "A tool call exceeded the timeout threshold.",
    },
    {
        "dimension": ScoringDimension.tool_failures,
        "event_name": "tool_call_retry_success",
        "amount": -2,
        "severity": PenaltySeverity.minor,
        "trigger_type": PenaltyTriggerType.structural,
        "description": "A tool call failed but succeeded on retry.",
    },
    {
        "dimension": ScoringDimension.tool_failures,
        "event_name": "ignored_tool_failure",
        "amount": -15,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "Agent continued without retry or acknowledgment after a tool failure.",
    },
    # Factual Grounding (weight 0.20)
    {
        "dimension": ScoringDimension.factual_grounding,
        "event_name": "ungrounded_claim",
        "amount": -15,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "A claim in the output is not supported by any tool call result.",
    },
    {
        "dimension": ScoringDimension.factual_grounding,
        "event_name": "contradicts_source",
        "amount": -25,
        "severity": PenaltySeverity.critical,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "Output contradicts information from a tool call result.",
    },
    {
        "dimension": ScoringDimension.factual_grounding,
        "event_name": "numeric_mismatch",
        "amount": -20,
        "severity": PenaltySeverity.critical,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "A numeric value in the output does not match the source data.",
    },
    {
        "dimension": ScoringDimension.factual_grounding,
        "event_name": "hallucinated_entity",
        "amount": -20,
        "severity": PenaltySeverity.critical,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "Output references an entity not found in any tool call result.",
    },
    # Thought Process (weight 0.15)
    {
        "dimension": ScoringDimension.thought_process,
        "event_name": "blind_tool_use",
        "amount": -5,
        "severity": PenaltySeverity.minor,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "A tool call has no preceding reasoning step.",
    },
    {
        "dimension": ScoringDimension.thought_process,
        "event_name": "reasoning_contradicts_action",
        "amount": -10,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "The reasoning step contradicts the subsequent action taken.",
    },
    {
        "dimension": ScoringDimension.thought_process,
        "event_name": "no_conclusion_explanation",
        "amount": -15,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "Final conclusion is not explained or justified.",
    },
    {
        "dimension": ScoringDimension.thought_process,
        "event_name": "ignores_relevant_data",
        "amount": -10,
        "severity": PenaltySeverity.moderate,
        "trigger_type": PenaltyTriggerType.slm_assisted,
        "description": "Relevant tool data is not incorporated into reasoning.",
    },
]


# Need Scorecard import for relationship
from models.eval import Scorecard  # noqa: E402, TC001
