"""Audit logging service for enterprise compliance (SOC 2 / ISO 27001).

Registers event bus handlers that write to the ClickHouse audit_log table.
Only active when DEPLOYMENT_MODE=enterprise.
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from services.clickhouse import _query
from services.events import (
    AgentLifecycleEvent,
    AlertRuleChanged,
    LoginFailure,
    LoginSuccess,
    RoleChanged,
    SettingsChanged,
    UserCreated,
    UserDeleted,
    bus,
)

logger = logging.getLogger("observal.ee.audit")


async def _insert_audit_row(
    *,
    actor_id: str,
    actor_email: str,
    actor_role: str = "",
    action: str,
    resource_type: str,
    resource_id: str = "",
    resource_name: str = "",
    http_method: str = "",
    http_path: str = "",
    status_code: int = 0,
    ip_address: str = "",
    user_agent: str = "",
    detail: str = "",
):
    """Insert a single row into the audit_log ClickHouse table."""
    event_id = str(uuid.uuid4())
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    sql = """INSERT INTO audit_log
        (event_id, timestamp, actor_id, actor_email, actor_role, action,
         resource_type, resource_id, resource_name, http_method, http_path,
         status_code, ip_address, user_agent, detail)
        VALUES
        ({eid:UUID}, {ts:DateTime64(3, 'UTC')}, {aid:String}, {aemail:String},
         {arole:String}, {action:String}, {rtype:String}, {rid:String},
         {rname:String}, {hmethod:String}, {hpath:String}, {scode:UInt16},
         {ip:String}, {ua:String}, {det:String})"""

    params = {
        "param_eid": event_id,
        "param_ts": ts,
        "param_aid": actor_id,
        "param_aemail": actor_email,
        "param_arole": actor_role,
        "param_action": action,
        "param_rtype": resource_type,
        "param_rid": resource_id,
        "param_rname": resource_name,
        "param_hmethod": http_method,
        "param_hpath": http_path,
        "param_scode": str(status_code),
        "param_ip": ip_address,
        "param_ua": user_agent,
        "param_det": detail,
    }

    try:
        await _query(sql, params)
    except Exception:
        logger.exception("Failed to insert audit log row")


def register_audit_handlers():
    """Register event bus handlers for audit logging. Called during enterprise startup."""

    @bus.on(UserCreated)
    async def _audit_user_created(event: UserCreated):
        await _insert_audit_row(
            actor_id=event.user_id,
            actor_email=event.email,
            actor_role=event.role,
            action="user.created",
            resource_type="user",
            resource_id=event.user_id,
            resource_name=event.email,
            detail=json.dumps({"is_demo": event.is_demo}),
        )

    @bus.on(UserDeleted)
    async def _audit_user_deleted(event: UserDeleted):
        await _insert_audit_row(
            actor_id=event.user_id,
            actor_email=event.email,
            action="user.deleted",
            resource_type="user",
            resource_id=event.user_id,
            resource_name=event.email,
        )

    @bus.on(LoginSuccess)
    async def _audit_login_success(event: LoginSuccess):
        await _insert_audit_row(
            actor_id=event.user_id,
            actor_email=event.email,
            action="auth.login_success",
            resource_type="session",
            detail=json.dumps({"method": event.method}),
        )

    @bus.on(LoginFailure)
    async def _audit_login_failure(event: LoginFailure):
        await _insert_audit_row(
            actor_id="",
            actor_email=event.email,
            action="auth.login_failure",
            resource_type="session",
            detail=json.dumps({"method": event.method, "reason": event.reason}),
        )

    @bus.on(RoleChanged)
    async def _audit_role_changed(event: RoleChanged):
        await _insert_audit_row(
            actor_id=event.user_id,
            actor_email=event.email,
            action="user.role_changed",
            resource_type="user",
            resource_id=event.user_id,
            resource_name=event.email,
            detail=json.dumps({"old_role": event.old_role, "new_role": event.new_role}),
        )

    @bus.on(SettingsChanged)
    async def _audit_settings_changed(event: SettingsChanged):
        await _insert_audit_row(
            actor_id="system",
            actor_email="",
            action="settings.changed",
            resource_type="config",
            resource_name=event.key,
            detail=json.dumps({"value": event.value}),
        )

    @bus.on(AlertRuleChanged)
    async def _audit_alert_changed(event: AlertRuleChanged):
        await _insert_audit_row(
            actor_id=event.actor_id,
            actor_email=event.actor_email,
            action=f"alert.{event.action}",
            resource_type="alert_rule",
            resource_id=event.alert_id,
        )

    @bus.on(AgentLifecycleEvent)
    async def _audit_agent_lifecycle(event: AgentLifecycleEvent):
        await _insert_audit_row(
            actor_id=event.actor_id,
            actor_email=event.actor_email,
            action=f"agent.{event.action}",
            resource_type="agent",
            resource_id=event.agent_id,
        )

    logger.info("Audit logging handlers registered (%d event types)", 8)
