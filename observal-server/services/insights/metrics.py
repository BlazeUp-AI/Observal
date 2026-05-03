"""Deterministic metrics computation from ClickHouse telemetry."""

import asyncio

import structlog

from services.clickhouse import _query
from services.insights.pricing import compute_cost_summary

logger = structlog.get_logger(__name__)

# Subquery to find all session IDs belonging to an agent.
# Matches sessions where either agent_type or agent_name equals the registry name.
_SESSIONS_SUBQUERY = """
    SELECT DISTINCT LogAttributes['session.id']
    FROM otel_logs
    WHERE (LogAttributes['agent_type'] = {aname:String}
           OR LogAttributes['agent_name'] = {aname:String})
      AND Timestamp >= {t_start:String}
      AND Timestamp <= {t_end:String}
      AND LogAttributes['session.id'] != ''
"""


async def get_session_overview(agent_name: str, start: str, end: str) -> dict:
    """Count sessions and unique users for the agent in the time window."""
    sql = f"""
        SELECT
            count(DISTINCT LogAttributes['session.id']) AS total_sessions,
            count(DISTINCT LogAttributes['user.id']) AS unique_users,
            min(Timestamp) AS first_session,
            max(Timestamp) AS last_session
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else {}
    except Exception as e:
        logger.error("insight_session_overview_failed", error=str(e))
        return {}


async def get_token_aggregates(agent_name: str, start: str, end: str) -> dict:
    """Aggregate token counts from otel_logs for this agent's sessions."""
    sql = f"""
        SELECT
            sum(toUInt64OrZero(LogAttributes['input_tokens'])) AS total_input_tokens,
            sum(toUInt64OrZero(LogAttributes['output_tokens'])) AS total_output_tokens,
            sum(toUInt64OrZero(LogAttributes['input_tokens'])) + sum(toUInt64OrZero(LogAttributes['output_tokens'])) AS total_tokens,
            sum(toUInt64OrZero(LogAttributes['cache_read_tokens'])) AS total_cache_read_tokens,
            sum(toUInt64OrZero(LogAttributes['cache_creation_tokens'])) AS total_cache_write_tokens
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else {}
    except Exception as e:
        logger.error("insight_token_aggregates_failed", error=str(e))
        return {}


async def get_latency_and_duration(agent_name: str, start: str, end: str) -> dict:
    """Compute session duration stats from otel_logs timestamps."""
    sql = f"""
        SELECT
            count() AS session_count,
            avg(duration_s) AS avg_duration_seconds,
            quantile(0.5)(duration_s) AS p50_duration_seconds,
            quantile(0.9)(duration_s) AS p90_duration_seconds
        FROM (
            SELECT
                dateDiff('second', min(Timestamp), max(Timestamp)) AS duration_s
            FROM otel_logs
            WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
              AND Timestamp >= {{t_start:String}}
              AND Timestamp <= {{t_end:String}}
            GROUP BY LogAttributes['session.id']
        )
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[0] if data else {}
    except Exception as e:
        logger.error("insight_latency_failed", error=str(e))
        return {}


async def get_error_breakdown(agent_name: str, start: str, end: str) -> dict:
    """Get tool call success/error rates from otel_logs."""
    sql = f"""
        SELECT
            count() AS total_events,
            countIf(LogAttributes['event.name'] = 'hook_posttooluse') AS total_tool_calls,
            countIf(LogAttributes['event.name'] = 'hook_stopfailure') AS failure_stops,
            countIf(LogAttributes['error'] != '') AS error_events
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        data = r.json().get("data", [])
        row = data[0] if data else {}
        total = int(row.get("total_tool_calls", 0))
        errors = int(row.get("error_events", 0))
        row["error_rate"] = round(errors / total, 4) if total > 0 else 0
        return row
    except Exception as e:
        logger.error("insight_error_breakdown_failed", error=str(e))
        return {}


async def get_tool_usage(agent_name: str, start: str, end: str) -> list[dict]:
    """Get top tools by invocation count from otel_logs."""
    sql = f"""
        SELECT
            LogAttributes['tool_name'] AS name,
            count() AS invocations,
            countIf(LogAttributes['error'] != '') AS errors
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
          AND LogAttributes['event.name'] IN ('hook_posttooluse', 'tool_result')
          AND LogAttributes['tool_name'] != ''
        GROUP BY name
        ORDER BY invocations DESC
        LIMIT 20
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error("insight_tool_usage_failed", error=str(e))
        return []


async def get_session_details(agent_name: str, start: str, end: str) -> list[dict]:
    """Get per-session stats from otel_logs."""
    sql = f"""
        SELECT
            LogAttributes['session.id'] AS session_id,
            dateDiff('second', min(Timestamp), max(Timestamp)) AS duration_seconds,
            greatest(
                countIf(LogAttributes['event.name'] = 'user_prompt'),
                countIf(LogAttributes['event.name'] = 'hook_userpromptsubmit')
            ) AS prompt_count,
            greatest(
                countIf(LogAttributes['event.name'] = 'tool_result'),
                countIf(LogAttributes['event.name'] = 'hook_posttooluse')
            ) AS tool_call_count,
            sum(toUInt64OrZero(LogAttributes['input_tokens'])) AS input_tokens,
            sum(toUInt64OrZero(LogAttributes['output_tokens'])) AS output_tokens
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
        GROUP BY session_id
        ORDER BY min(Timestamp) DESC
        LIMIT 200
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error("insight_session_details_failed", error=str(e))
        return []


async def get_per_session_tokens(agent_name: str, start: str, end: str) -> list[dict]:
    """Get per-session token breakdown with model name for cost computation."""
    sql = f"""
        SELECT
            LogAttributes['session.id'] AS session_id,
            sum(toUInt64OrZero(LogAttributes['input_tokens'])) AS input_tokens,
            sum(toUInt64OrZero(LogAttributes['output_tokens'])) AS output_tokens,
            sum(toUInt64OrZero(LogAttributes['cache_read_tokens'])) AS cache_read,
            sum(toUInt64OrZero(LogAttributes['cache_creation_tokens'])) AS cache_write,
            anyIf(LogAttributes['model'], LogAttributes['model'] != '') AS model
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
        GROUP BY session_id
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error("insight_per_session_tokens_failed", error=str(e))
        return []


def categorize_error(error_text: str) -> str:
    """Categorize a tool error into a high-level bucket."""
    lower = error_text.lower()
    if "exit code" in lower:
        return "command_failed"
    if "rejected" in lower or "doesn't want" in lower or "denied" in lower:
        return "user_rejected"
    if "string to replace not found" in lower or "not unique" in lower:
        return "edit_failed"
    if "modified since read" in lower:
        return "file_changed"
    if "exceeds maximum" in lower or "too large" in lower:
        return "file_too_large"
    if "file not found" in lower or "does not exist" in lower or "no such file" in lower:
        return "file_not_found"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if "permission" in lower:
        return "permission_denied"
    return "other"


async def get_tool_error_categories(agent_name: str, start: str, end: str) -> dict:
    """Get tool errors with their text for categorization in Python."""
    sql = f"""
        SELECT
            LogAttributes['tool_name'] AS tool_name,
            LogAttributes['error'] AS error_text
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
          AND LogAttributes['error'] != ''
        LIMIT 500
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        rows = r.json().get("data", [])

        # Categorize errors
        categories: dict[str, int] = {}
        by_tool: dict[str, dict[str, int]] = {}
        for row in rows:
            cat = categorize_error(row.get("error_text", ""))
            categories[cat] = categories.get(cat, 0) + 1
            tool = row.get("tool_name", "unknown")
            if tool not in by_tool:
                by_tool[tool] = {}
            by_tool[tool][cat] = by_tool[tool].get(cat, 0) + 1

        return {
            "total_categorized": len(rows),
            "categories": categories,
            "by_tool": by_tool,
        }
    except Exception as e:
        logger.error("insight_tool_error_categories_failed", error=str(e))
        return {"total_categorized": 0, "categories": {}, "by_tool": {}}


async def get_interruption_metrics(agent_name: str, start: str, end: str) -> dict:
    """Get stop reason counts and user interruption metrics."""
    sql = f"""
        SELECT
            LogAttributes['stop_reason'] AS stop_reason,
            count() AS cnt
        FROM otel_logs
        WHERE LogAttributes['session.id'] IN ({_SESSIONS_SUBQUERY})
          AND Timestamp >= {{t_start:String}}
          AND Timestamp <= {{t_end:String}}
          AND LogAttributes['stop_reason'] != ''
        GROUP BY stop_reason
        ORDER BY cnt DESC
        FORMAT JSON
    """
    params = {
        "param_aname": agent_name,
        "param_t_start": start,
        "param_t_end": end,
    }
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        rows = r.json().get("data", [])
        stop_reasons = {row["stop_reason"]: int(row["cnt"]) for row in rows}
        user_interruptions = stop_reasons.get("user_interrupt", 0) + stop_reasons.get("interrupted", 0)
        return {
            "stop_reasons": stop_reasons,
            "user_interruptions": user_interruptions,
            "total_stops": sum(stop_reasons.values()),
        }
    except Exception as e:
        logger.error("insight_interruption_metrics_failed", error=str(e))
        return {"stop_reasons": {}, "user_interruptions": 0, "total_stops": 0}


async def compute_all_metrics(agent_name: str, start: str, end: str) -> dict:
    """Run all metric queries in parallel and return combined results."""
    (
        overview,
        tokens,
        duration,
        errors,
        tools,
        sessions,
        per_session_tokens,
        tool_errors,
        interruptions,
    ) = await asyncio.gather(
        get_session_overview(agent_name, start, end),
        get_token_aggregates(agent_name, start, end),
        get_latency_and_duration(agent_name, start, end),
        get_error_breakdown(agent_name, start, end),
        get_tool_usage(agent_name, start, end),
        get_session_details(agent_name, start, end),
        get_per_session_tokens(agent_name, start, end),
        get_tool_error_categories(agent_name, start, end),
        get_interruption_metrics(agent_name, start, end),
    )

    # Compute cost summary from per-session token data
    cost = compute_cost_summary(per_session_tokens)

    return {
        "overview": overview,
        "tokens": tokens,
        "duration": duration,
        "errors": errors,
        "tools": tools,
        "sessions": sessions,
        "cost": cost,
        "tool_errors": tool_errors,
        "interruptions": interruptions,
    }
