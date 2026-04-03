import uuid

from pydantic import BaseModel


class McpMetrics(BaseModel):
    listing_id: uuid.UUID
    total_downloads: int
    total_calls: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: int
    p90_latency_ms: int
    p99_latency_ms: int


class AgentMetrics(BaseModel):
    agent_id: uuid.UUID
    total_interactions: int
    total_downloads: int
    acceptance_rate: float
    avg_tool_calls: float
    avg_latency_ms: float


class TimeSeriesPoint(BaseModel):
    date: str
    value: int


class OverviewStats(BaseModel):
    total_mcps: int
    total_agents: int
    total_users: int
    total_tool_calls_today: int
    total_agent_interactions_today: int


class TopItem(BaseModel):
    id: uuid.UUID
    name: str
    value: float


class TrendPoint(BaseModel):
    date: str
    submissions: int
    users: int
