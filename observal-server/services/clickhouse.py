import logging
from urllib.parse import urlparse

import httpx

from config import settings

logger = logging.getLogger(__name__)

_parsed = urlparse(settings.CLICKHOUSE_URL.replace("clickhouse://", "http://"))
CLICKHOUSE_HTTP = f"http://{_parsed.hostname}:{_parsed.port or 8123}"
CLICKHOUSE_DB = _parsed.path.strip("/") or "default"
CLICKHOUSE_USER = _parsed.username or "default"
CLICKHOUSE_PASSWORD = _parsed.password or ""

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10)
    return _client


async def _query(sql: str, params: dict | None = None):
    client = _get_client()
    query_params = {
        "database": CLICKHOUSE_DB,
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
    }
    if params:
        query_params.update(params)
    return await client.post(CLICKHOUSE_HTTP, content=sql, params=query_params)


INIT_SQL = [
    # Legacy tables (kept for backward compat)
    """CREATE TABLE IF NOT EXISTS mcp_tool_calls (
        event_id UUID,
        timestamp DateTime64(3, 'UTC'),
        mcp_server_id String,
        tool_name String,
        input_params String,
        response String,
        latency_ms UInt32,
        status String,
        user_action String,
        session_id String,
        user_id String,
        ide String
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (mcp_server_id, timestamp)""",
    """CREATE TABLE IF NOT EXISTS agent_interactions (
        event_id UUID,
        timestamp DateTime64(3, 'UTC'),
        agent_id String,
        session_id String,
        tool_calls UInt32,
        user_action String,
        latency_ms UInt32,
        user_id String,
        ide String
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (agent_id, timestamp)""",
    # New telemetry tables (Phase 1)
    """CREATE TABLE IF NOT EXISTS traces (
        trace_id        String,
        parent_trace_id Nullable(String),
        project_id      String,
        mcp_id          Nullable(String),
        agent_id        Nullable(String),
        user_id         String,
        session_id      Nullable(String),
        ide             LowCardinality(String),
        environment     LowCardinality(String) DEFAULT 'default',
        start_time      DateTime64(3),
        end_time        Nullable(DateTime64(3)),
        trace_type      LowCardinality(String) DEFAULT 'mcp',
        name            String DEFAULT '',
        metadata        Map(LowCardinality(String), String),
        tags            Array(String),
        input           Nullable(String) CODEC(ZSTD(3)),
        output          Nullable(String) CODEC(ZSTD(3)),
        created_at      DateTime64(3) DEFAULT now(),
        event_ts        DateTime64(3),
        is_deleted      UInt8 DEFAULT 0,
        INDEX idx_trace_id trace_id TYPE bloom_filter(0.001) GRANULARITY 1,
        INDEX idx_parent_trace_id parent_trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_project_id project_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_mcp_id mcp_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_agent_id agent_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_user_id user_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_session_id session_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_trace_type trace_type TYPE bloom_filter(0.01) GRANULARITY 1
    ) ENGINE = ReplacingMergeTree(event_ts, is_deleted)
    PARTITION BY toYYYYMM(start_time)
    PRIMARY KEY (project_id, user_id, toDate(start_time))
    ORDER BY (project_id, user_id, toDate(start_time), trace_id)""",
    """CREATE TABLE IF NOT EXISTS spans (
        span_id                 String,
        trace_id                String,
        parent_span_id          Nullable(String),
        project_id              String,
        mcp_id                  Nullable(String),
        agent_id                Nullable(String),
        user_id                 String,
        type                    LowCardinality(String),
        name                    String,
        method                  String DEFAULT '',
        input                   Nullable(String) CODEC(ZSTD(3)),
        output                  Nullable(String) CODEC(ZSTD(3)),
        error                   Nullable(String) CODEC(ZSTD(3)),
        start_time              DateTime64(3),
        end_time                Nullable(DateTime64(3)),
        latency_ms              Nullable(UInt32),
        status                  LowCardinality(String) DEFAULT 'success',
        level                   LowCardinality(String) DEFAULT 'DEFAULT',
        token_count_input       Nullable(UInt32),
        token_count_output      Nullable(UInt32),
        token_count_total       Nullable(UInt32),
        cost                    Nullable(Float64),
        cpu_ms                  Nullable(UInt32),
        memory_mb               Nullable(Float32),
        hop_count               Nullable(UInt8),
        entities_retrieved      Nullable(UInt16),
        relationships_used      Nullable(UInt16),
        retry_count             Nullable(UInt8),
        tools_available         Nullable(UInt16),
        tool_schema_valid       Nullable(UInt8),
        ide                     LowCardinality(String) DEFAULT '',
        environment             LowCardinality(String) DEFAULT 'default',
        metadata                Map(LowCardinality(String), String),
        created_at              DateTime64(3) DEFAULT now(),
        event_ts                DateTime64(3),
        is_deleted              UInt8 DEFAULT 0,
        INDEX idx_span_id span_id TYPE bloom_filter(0.001) GRANULARITY 1,
        INDEX idx_trace_id trace_id TYPE bloom_filter(0.001) GRANULARITY 1,
        INDEX idx_project_id project_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_name name TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_type type TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_status status TYPE bloom_filter(0.01) GRANULARITY 1
    ) ENGINE = ReplacingMergeTree(event_ts, is_deleted)
    PARTITION BY toYYYYMM(start_time)
    PRIMARY KEY (project_id, user_id, type, toDate(start_time))
    ORDER BY (project_id, user_id, type, toDate(start_time), span_id)""",
    """CREATE TABLE IF NOT EXISTS scores (
        score_id        String,
        trace_id        Nullable(String),
        span_id         Nullable(String),
        project_id      String,
        mcp_id          Nullable(String),
        agent_id        Nullable(String),
        user_id         String,
        name            String,
        source          LowCardinality(String),
        data_type       LowCardinality(String),
        value           Float64,
        string_value    Nullable(String),
        comment         Nullable(String) CODEC(ZSTD(1)),
        eval_template_id Nullable(String),
        eval_config_id  Nullable(String),
        eval_run_id     Nullable(String),
        environment     LowCardinality(String) DEFAULT 'default',
        metadata        Map(LowCardinality(String), String),
        timestamp       DateTime64(3),
        created_at      DateTime64(3) DEFAULT now(),
        event_ts        DateTime64(3),
        is_deleted      UInt8 DEFAULT 0,
        INDEX idx_score_id score_id TYPE bloom_filter(0.001) GRANULARITY 1,
        INDEX idx_trace_id trace_id TYPE bloom_filter(0.001) GRANULARITY 1,
        INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_project_id project_id TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_name name TYPE bloom_filter(0.01) GRANULARITY 1,
        INDEX idx_source source TYPE bloom_filter(0.01) GRANULARITY 1
    ) ENGINE = ReplacingMergeTree(event_ts, is_deleted)
    PARTITION BY toYYYYMM(timestamp)
    PRIMARY KEY (project_id, user_id, toDate(timestamp), name)
    ORDER BY (project_id, user_id, toDate(timestamp), name, score_id)""",
]


async def init_clickhouse():
    """Create ClickHouse tables if they don't exist."""
    for stmt in INIT_SQL:
        try:
            await _query(stmt)
        except Exception as e:
            logger.warning(f"ClickHouse init failed: {e}")


async def insert_tool_call(event: dict):
    sql = """INSERT INTO mcp_tool_calls
        (event_id, timestamp, mcp_server_id, tool_name, input_params, response, latency_ms, status, user_action, session_id, user_id, ide)
        VALUES
        ({event_id:String}, {ts:String}, {mcp_server_id:String}, {tool_name:String}, {input_params:String}, {response:String}, {latency_ms:UInt32}, {status:String}, {user_action:String}, {session_id:String}, {user_id:String}, {ide:String})"""
    params = {
        "param_event_id": event["event_id"],
        "param_ts": event["timestamp"],
        "param_mcp_server_id": event.get("mcp_server_id", ""),
        "param_tool_name": event.get("tool_name", ""),
        "param_input_params": event.get("input_params", ""),
        "param_response": event.get("response", ""),
        "param_latency_ms": str(event.get("latency_ms", 0)),
        "param_status": event.get("status", ""),
        "param_user_action": event.get("user_action", ""),
        "param_session_id": event.get("session_id", ""),
        "param_user_id": event.get("user_id", ""),
        "param_ide": event.get("ide", ""),
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"ClickHouse insert_tool_call failed: {e}")
        raise


async def insert_agent_interaction(event: dict):
    sql = """INSERT INTO agent_interactions
        (event_id, timestamp, agent_id, session_id, tool_calls, user_action, latency_ms, user_id, ide)
        VALUES
        ({event_id:String}, {ts:String}, {agent_id:String}, {session_id:String}, {tool_calls:UInt32}, {user_action:String}, {latency_ms:UInt32}, {user_id:String}, {ide:String})"""
    params = {
        "param_event_id": event["event_id"],
        "param_ts": event["timestamp"],
        "param_agent_id": event.get("agent_id", ""),
        "param_session_id": event.get("session_id", ""),
        "param_tool_calls": str(event.get("tool_calls", 0)),
        "param_user_action": event.get("user_action", ""),
        "param_latency_ms": str(event.get("latency_ms", 0)),
        "param_user_id": event.get("user_id", ""),
        "param_ide": event.get("ide", ""),
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"ClickHouse insert_agent_interaction failed: {e}")
        raise


async def query_recent_events(minutes: int = 60) -> dict:
    """Get event counts from the last N minutes."""
    minutes = int(minutes)
    tool_count = 0
    agent_count = 0

    try:
        r = await _query(
            f"SELECT count() as cnt FROM mcp_tool_calls WHERE timestamp > now() - INTERVAL {minutes} MINUTE FORMAT JSON"
        )
        if r.status_code == 200:
            tool_count = int(r.json().get("data", [{}])[0].get("cnt", 0))
    except Exception as e:
        logger.warning(f"ClickHouse query tool_calls failed: {e}")

    try:
        r = await _query(
            f"SELECT count() as cnt FROM agent_interactions WHERE timestamp > now() - INTERVAL {minutes} MINUTE FORMAT JSON"
        )
        if r.status_code == 200:
            agent_count = int(r.json().get("data", [{}])[0].get("cnt", 0))
    except Exception as e:
        logger.warning(f"ClickHouse query agent_interactions failed: {e}")

    return {"tool_call_events": tool_count, "agent_interaction_events": agent_count}
