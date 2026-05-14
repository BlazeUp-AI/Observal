# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Vishnu Muthiah <vishnu.muthiah04@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Alert evaluation engine: periodic metric checks and webhook delivery."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from database import async_session
from models.alert import AlertRule
from models.alert_history import AlertHistory
from services.clickhouse import _query
from services.ssrf_guard import is_private_url  # noqa: F401 -- re-exported for callers

logger = logging.getLogger(__name__)

LOOKBACK_MINUTES = 5
WEBHOOK_TIMEOUT = 5


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


async def _deliver_webhook_signed(
    url: str, secret: str, payload: dict, alert_rule_id: uuid.UUID
) -> tuple[int | None, str | None]:
    """Deliver a signed webhook using the webhook_delivery service.

    Returns (status_code, error) tuple for AlertHistory compatibility.
    If secret is empty (legacy rule), delivers without signature (AD-4).
    """
    from services.webhook_delivery import deliver_webhook

    result = await deliver_webhook(
        webhook_url=url,
        webhook_secret=secret,
        payload=payload,
        alert_rule_id=alert_rule_id,
    )
    if result.success:
        return result.status_code, None
    return result.status_code, result.error


def _condition_met(condition: str, value: float, threshold: float) -> bool:
    """Check if the alert condition is met."""
    if condition == "above":
        return value > threshold
    elif condition == "below":
        return value < threshold
    return False


async def evaluate_alerts(ctx: dict) -> None:
    """Main arq cron job: evaluate all active alert rules and fire webhooks."""
    from services.webhook_delivery import flush_delivery_records

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
                    # AD-3: secret resolved here at evaluation time, not later
                    status_code, error = await _deliver_webhook_signed(
                        rule.webhook_url, rule.webhook_secret, payload, rule.id
                    )
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

    # AD-1: Batch-flush delivery records to ClickHouse at end of cycle
    await flush_delivery_records()
    logger.info("Alert evaluation cycle complete")
