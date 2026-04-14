"""Alert evaluation engine: periodic metric checks and webhook delivery."""

import ipaddress
import logging
import socket
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from database import async_session
from models.alert import AlertRule
from models.alert_history import AlertHistory
from services.clickhouse import _query

logger = logging.getLogger(__name__)

_PRIVATE_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
]

LOOKBACK_MINUTES = 5
WEBHOOK_TIMEOUT = 5


def is_private_url(url: str) -> bool:
    """Check if a URL resolves to a private/internal IP address (SSRF protection)."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return True
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not resolved:
                return True
            addr = ipaddress.ip_address(resolved[0][4][0])
        except (socket.gaierror, OSError):
            return True
    return any(addr in cidr for cidr in _PRIVATE_CIDRS)


async def _query_error_rate(target_type: str, target_id: str, lookback_minutes: int) -> float | None:
    """Query the error rate from ClickHouse spans table."""
    sql = (
        "SELECT countIf(status='error') / count(*) AS error_rate "
        "FROM spans "
        "WHERE start_time > now() - INTERVAL {lookback:UInt32} MINUTE"
    )
    params: dict[str, str] = {"param_lookback": str(lookback_minutes)}
    if target_type == "agent":
        sql += " AND agent_id = {target_id:String}"
        params["param_target_id"] = target_id
    elif target_type == "mcp":
        sql += " AND mcp_id = {target_id:String}"
        params["param_target_id"] = target_id
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        text = r.text.strip()
        if not text:
            return None
        return float(text)
    except Exception as e:
        logger.error("ClickHouse error_rate query failed: %s", e)
        return None


async def _query_latency_p99(target_type: str, target_id: str, lookback_minutes: int) -> float | None:
    """Query the p99 latency from ClickHouse spans table."""
    sql = (
        "SELECT quantile(0.99)(latency_ms) AS latency_p99 "
        "FROM spans "
        "WHERE start_time > now() - INTERVAL {lookback:UInt32} MINUTE"
    )
    params: dict[str, str] = {"param_lookback": str(lookback_minutes)}
    if target_type == "agent":
        sql += " AND agent_id = {target_id:String}"
        params["param_target_id"] = target_id
    elif target_type == "mcp":
        sql += " AND mcp_id = {target_id:String}"
        params["param_target_id"] = target_id
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        text = r.text.strip()
        if not text:
            return None
        return float(text)
    except Exception as e:
        logger.error("ClickHouse latency_p99 query failed: %s", e)
        return None


async def _query_token_usage(target_type: str, target_id: str, lookback_minutes: int) -> float | None:
    """Query total token usage from ClickHouse spans table."""
    sql = (
        "SELECT sum(token_count_total) AS token_usage "
        "FROM spans "
        "WHERE start_time > now() - INTERVAL {lookback:UInt32} MINUTE"
    )
    params: dict[str, str] = {"param_lookback": str(lookback_minutes)}
    if target_type == "agent":
        sql += " AND agent_id = {target_id:String}"
        params["param_target_id"] = target_id
    elif target_type == "mcp":
        sql += " AND mcp_id = {target_id:String}"
        params["param_target_id"] = target_id
    try:
        r = await _query(sql, params)
        r.raise_for_status()
        text = r.text.strip()
        if not text:
            return None
        return float(text)
    except Exception as e:
        logger.error("ClickHouse token_usage query failed: %s", e)
        return None


async def _query_metric(metric: str, target_type: str, target_id: str, lookback_minutes: int) -> float | None:
    """Dispatch to the appropriate metric query helper."""
    if metric == "error_rate":
        return await _query_error_rate(target_type, target_id, lookback_minutes)
    elif metric == "latency_p99":
        return await _query_latency_p99(target_type, target_id, lookback_minutes)
    elif metric == "token_usage":
        return await _query_token_usage(target_type, target_id, lookback_minutes)
    else:
        logger.warning("Unknown metric: %s", metric)
        return None


async def _deliver_webhook(url: str, payload: dict) -> tuple[int | None, str | None]:
    """POST JSON payload to a webhook URL with SSRF protection and retry."""
    if not url:
        return None, "empty webhook URL"
    if is_private_url(url):
        return None, "SSRF: webhook URL resolves to private network"
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        last_error: str | None = None
        for attempt in range(2):
            try:
                resp = await client.post(url, json=payload)
                return resp.status_code, None
            except Exception as e:
                last_error = f"attempt {attempt + 1}: {e}"
                logger.warning("Webhook delivery to %s failed (%s)", url, last_error)
    return None, last_error


def _condition_met(condition: str, value: float, threshold: float) -> bool:
    """Check if the alert condition is met."""
    if condition == "above":
        return value > threshold
    elif condition == "below":
        return value < threshold
    return False


async def evaluate_alerts(ctx: dict) -> None:
    """Main arq cron job: evaluate all active alert rules and fire webhooks."""
    logger.info("Starting alert evaluation cycle")
    async with async_session() as db:
        stmt = select(AlertRule).where(AlertRule.status == "active")
        result = await db.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            try:
                value = await _query_metric(
                    rule.metric,
                    rule.target_type,
                    rule.target_id,
                    LOOKBACK_MINUTES,
                )
                if value is None:
                    continue
                if not _condition_met(rule.condition, value, rule.threshold):
                    continue

                now = datetime.now(UTC)
                status_code: int | None = None
                error: str | None = None
                delivery_status = "pending"

                if rule.webhook_url:
                    payload = {
                        "alert_rule_id": str(rule.id),
                        "alert_name": rule.name,
                        "metric": rule.metric,
                        "metric_value": value,
                        "threshold": rule.threshold,
                        "condition": rule.condition,
                        "target_type": rule.target_type,
                        "target_id": rule.target_id,
                        "fired_at": now.isoformat(),
                    }
                    status_code, error = await _deliver_webhook(rule.webhook_url, payload)
                    delivery_status = "delivered" if error is None else "failed"
                else:
                    delivery_status = "delivered"

                history = AlertHistory(
                    id=uuid.uuid4(),
                    alert_rule_id=rule.id,
                    metric_value=value,
                    threshold=rule.threshold,
                    condition=rule.condition,
                    fired_at=now,
                    delivery_status=delivery_status,
                    response_code=status_code,
                    error=error,
                )
                db.add(history)
                rule.last_triggered = now
                await db.commit()

                logger.info(
                    "Alert '%s' fired: %s=%s (threshold=%s, condition=%s, delivery=%s)",
                    rule.name,
                    rule.metric,
                    value,
                    rule.threshold,
                    rule.condition,
                    delivery_status,
                )
            except Exception as e:
                logger.exception("Error evaluating alert rule %s: %s", rule.id, e)
    logger.info("Alert evaluation cycle complete")
