import uuid
from datetime import datetime

from pydantic import BaseModel

from models.insight_report import InsightReportStatus


class GenerateInsightRequest(BaseModel):
    period_days: int = 14


class InsightReportListItem(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    status: InsightReportStatus
    period_start: datetime
    period_end: datetime
    sessions_analyzed: int
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class InsightReportResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    triggered_by: uuid.UUID | None
    status: InsightReportStatus
    period_start: datetime
    period_end: datetime
    metrics: dict | None
    narrative: dict | None
    sessions_analyzed: int
    llm_model_used: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
