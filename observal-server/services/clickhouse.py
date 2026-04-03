import logging
from datetime import datetime, timezone
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


def _escape(val: str) -> str:
    """Escape single quotes for ClickHouse SQL strings."""
    return str(val).replace("\\", "\\\\").replace("'", "\\'")


def _nullable_str(val: str | None) -> str:
    """Format a value as a ClickHouse Nullable(String) literal."""
    if val is None:
        return "NULL"
    return f"'{_escape(val)}'"


def _nullable_uint(val: int | None) -> str:
    """Format a value as a ClickHouse Nullable(UInt*) literal."""
    if val is None:
        return "NULL"
    return str(int(val))


def _nullable_float(val: float | None) -> str:
    """Format a value as a ClickHouse Nullable(Float*) literal."""
    if val is None:
        return "NULL"
    return str(float(val))


def _map_literal(m: dict) -> str:
    """Format a dict as a ClickHouse Map literal."""
    if not m:
        return "map()"
    pairs = ", ".join(f"'{_escape(k)}', '{_escape(v)}'" for k, v in m.items())
    return f"map({pairs})"


def _array_literal(arr: list) -> str:
    """Format a list as a ClickHouse Array literal."""
    if not arr:
        return "[]"
    items = ", ".join(f"'{_escape(v)}'" for v in arr)
    return f"[{items}]"


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


def _now_ms() -> str:
    """Current UTC timestamp as ISO string with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


async def insert_traces(traces: list[dict]):
    """Batch insert traces into ClickHouse."""
    if not traces:
        return
    event_ts = _now_ms()
    rows = []
    for t in traces:
        rows.append(
            f"('{t['trace_id']}', {_nullable_str(t.get('parent_trace_id'))}, "
            f"'{t['project_id']}', {_nullable_str(t.get('mcp_id'))}, "
            f"{_nullable_str(t.get('agent_id'))}, '{t['user_id']}', "
            f"{_nullable_str(t.get('session_id'))}, '{t.get('ide', '')}', "
            f"'{t.get('environment', 'default')}', '{t['start_time']}', "
            f"{_nullable_str(t.get('end_time'))}, '{t.get('trace_type', 'mcp')}', "
            f"'{_escape(t.get('name', ''))}', {_map_literal(t.get('metadata', {}))}, "
            f"{_array_literal(t.get('tags', []))}, "
            f"{_nullable_str(t.get('input'))}, {_nullable_str(t.get('output'))}, "
            f"now(), '{event_ts}', 0)"
        )
    sql = (
        "INSERT INTO traces (trace_id, parent_trace_id, project_id, mcp_id, agent_id, "
        "user_id, session_id, ide, environment, start_time, end_time, trace_type, name, "
        "metadata, tags, input, output, created_at, event_ts, is_deleted) VALUES "
        + ", ".join(rows)
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"ClickHouse insert_traces failed: {e}")
        raise


async def insert_spans(spans: list[dict]):
    """Batch insert spans into ClickHouse."""
    if not spans:
        return
    event_ts = _now_ms()
    rows = []
    for s in spans:
        rows.append(
            f"('{s['span_id']}', '{s['trace_id']}', "
            f"{_nullable_str(s.get('parent_span_id'))}, '{s['project_id']}', "
            f"{_nullable_str(s.get('mcp_id'))}, {_nullable_str(s.get('agent_id'))}, "
            f"'{s['user_id']}', '{s['type']}', '{_escape(s['name'])}', "
            f"'{_escape(s.get('method', ''))}', "
            f"{_nullable_str(s.get('input'))}, {_nullable_str(s.get('output'))}, "
            f"{_nullable_str(s.get('error'))}, '{s['start_time']}', "
            f"{_nullable_str(s.get('end_time'))}, {_nullable_uint(s.get('latency_ms'))}, "
            f"'{s.get('status', 'success')}', '{s.get('level', 'DEFAULT')}', "
            f"{_nullable_uint(s.get('token_count_input'))}, "
            f"{_nullable_uint(s.get('token_count_output'))}, "
            f"{_nullable_uint(s.get('token_count_total'))}, "
            f"{_nullable_float(s.get('cost'))}, "
            f"{_nullable_uint(s.get('cpu_ms'))}, "
            f"{_nullable_float(s.get('memory_mb'))}, "
            f"{_nullable_uint(s.get('hop_count'))}, "
            f"{_nullable_uint(s.get('entities_retrieved'))}, "
            f"{_nullable_uint(s.get('relationships_used'))}, "
            f"{_nullable_uint(s.get('retry_count'))}, "
            f"{_nullable_uint(s.get('tools_available'))}, "
            f"{_nullable_uint(s.get('tool_schema_valid'))}, "
            f"'{s.get('ide', '')}', '{s.get('environment', 'default')}', "
            f"{_map_literal(s.get('metadata', {}))}, now(), '{event_ts}', 0)"
        )
    sql = (
        "INSERT INTO spans (span_id, trace_id, parent_span_id, project_id, mcp_id, "
        "agent_id, user_id, type, name, method, input, output, error, start_time, "
        "end_time, latency_ms, status, level, token_count_input, token_count_output, "
        "token_count_total, cost, cpu_ms, memory_mb, hop_count, entities_retrieved, "
        "relationships_used, retry_count, tools_available, tool_schema_valid, ide, "
        "environment, metadata, created_at, event_ts, is_deleted) VALUES "
        + ", ".join(rows)
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"ClickHouse insert_spans failed: {e}")
        raise


async def insert_scores(scores: list[dict]):
    """Batch insert scores into ClickHouse."""
    if not scores:
        return
    event_ts = _now_ms()
    rows = []
    for sc in scores:
        rows.append(
            f"('{sc['score_id']}', {_nullable_str(sc.get('trace_id'))}, "
            f"{_nullable_str(sc.get('span_id'))}, '{sc['project_id']}', "
            f"{_nullable_str(sc.get('mcp_id'))}, {_nullable_str(sc.get('agent_id'))}, "
            f"'{sc['user_id']}', '{_escape(sc['name'])}', "
            f"'{sc.get('source', 'api')}', '{sc.get('data_type', 'numeric')}', "
            f"{sc.get('value', 0)}, {_nullable_str(sc.get('string_value'))}, "
            f"{_nullable_str(sc.get('comment'))}, "
            f"{_nullable_str(sc.get('eval_template_id'))}, "
            f"{_nullable_str(sc.get('eval_config_id'))}, "
            f"{_nullable_str(sc.get('eval_run_id'))}, "
            f"'{sc.get('environment', 'default')}', "
            f"{_map_literal(sc.get('metadata', {}))}, "
            f"'{sc['timestamp']}', now(), '{event_ts}', 0)"
        )
    sql = (
        "INSERT INTO scores (score_id, trace_id, span_id, project_id, mcp_id, agent_id, "
        "user_id, name, source, data_type, value, string_value, comment, "
        "eval_template_id, eval_config_id, eval_run_id, environment, metadata, "
        "timestamp, created_at, event_ts, is_deleted) VALUES "
        + ", ".join(rows)
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"ClickHouse insert_scores failed: {e}")
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


# --- Query functions for new tables ---


async def query_traces(
    project_id: str,
    *,
    trace_type: str | None = None,
    mcp_id: str | None = None,
    agent_id: str | None = None,
    user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Query traces with optional filters."""
    conditions = [f"project_id = '{_escape(project_id)}'", "is_deleted = 0"]
    if trace_type:
        conditions.append(f"trace_type = '{_escape(trace_type)}'")
    if mcp_id:
        conditions.append(f"mcp_id = '{_escape(mcp_id)}'")
    if agent_id:
        conditions.append(f"agent_id = '{_escape(agent_id)}'")
    if user_id:
        conditions.append(f"user_id = '{_escape(user_id)}'")
    where = " AND ".join(conditions)
    sql = (
        f"SELECT * FROM traces FINAL WHERE {where} "
        f"ORDER BY start_time DESC LIMIT {int(limit)} OFFSET {int(offset)} FORMAT JSON"
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error(f"ClickHouse query_traces failed: {e}")
        return []


async def query_trace_by_id(project_id: str, trace_id: str) -> dict | None:
    """Get a single trace by ID."""
    sql = (
        f"SELECT * FROM traces FINAL WHERE project_id = '{_escape(project_id)}' "
        f"AND trace_id = '{_escape(trace_id)}' AND is_deleted = 0 LIMIT 1 FORMAT JSON"
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else None
    except Exception as e:
        logger.error(f"ClickHouse query_trace_by_id failed: {e}")
        return None


async def query_spans(
    project_id: str,
    trace_id: str,
    *,
    span_type: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Query spans for a trace with optional filters."""
    conditions = [
        f"project_id = '{_escape(project_id)}'",
        f"trace_id = '{_escape(trace_id)}'",
        "is_deleted = 0",
    ]
    if span_type:
        conditions.append(f"type = '{_escape(span_type)}'")
    if status:
        conditions.append(f"status = '{_escape(status)}'")
    where = " AND ".join(conditions)
    sql = (
        f"SELECT * FROM spans FINAL WHERE {where} "
        f"ORDER BY start_time ASC LIMIT {int(limit)} FORMAT JSON"
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error(f"ClickHouse query_spans failed: {e}")
        return []


async def query_span_by_id(project_id: str, span_id: str) -> dict | None:
    """Get a single span by ID."""
    sql = (
        f"SELECT * FROM spans FINAL WHERE project_id = '{_escape(project_id)}' "
        f"AND span_id = '{_escape(span_id)}' AND is_deleted = 0 LIMIT 1 FORMAT JSON"
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else None
    except Exception as e:
        logger.error(f"ClickHouse query_span_by_id failed: {e}")
        return None


async def query_scores(
    project_id: str,
    *,
    trace_id: str | None = None,
    span_id: str | None = None,
    source: str | None = None,
    name: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query scores with optional filters."""
    conditions = [f"project_id = '{_escape(project_id)}'", "is_deleted = 0"]
    if trace_id:
        conditions.append(f"trace_id = '{_escape(trace_id)}'")
    if span_id:
        conditions.append(f"span_id = '{_escape(span_id)}'")
    if source:
        conditions.append(f"source = '{_escape(source)}'")
    if name:
        conditions.append(f"name = '{_escape(name)}'")
    where = " AND ".join(conditions)
    sql = (
        f"SELECT * FROM scores FINAL WHERE {where} "
        f"ORDER BY timestamp DESC LIMIT {int(limit)} FORMAT JSON"
    )
    try:
        r = await _query(sql)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error(f"ClickHouse query_scores failed: {e}")
        return []
