import uuid
from datetime import datetime

from pydantic import BaseModel

from models.eval import EvalRunStatus


class ScorecardDimensionResponse(BaseModel):
    dimension: str
    score: float
    grade: str
    notes: str | None
    model_config = {"from_attributes": True}


class ScorecardResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    eval_run_id: uuid.UUID
    trace_id: str
    version: str
    overall_score: float
    overall_grade: str
    recommendations: str | None
    bottleneck: str | None
    evaluated_at: datetime
    dimensions: list[ScorecardDimensionResponse] = []
    # New structured scoring fields
    dimension_scores: dict | None = None
    composite_score: float | None = None
    display_score: float | None = None
    grade: str | None = None
    scoring_recommendations: list[str] | None = None
    penalty_count: int = 0
    model_config = {"from_attributes": True}


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    triggered_by: uuid.UUID
    status: EvalRunStatus
    traces_evaluated: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class EvalRunDetailResponse(EvalRunResponse):
    scorecards: list[ScorecardResponse] = []


class EvalRequest(BaseModel):
    trace_id: str | None = None  # Evaluate specific trace, or all recent if None
