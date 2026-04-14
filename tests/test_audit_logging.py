"""Tests for enterprise audit logging (SOC 2 / ISO 27001 compliance)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestRegisterAuditHandlers:
    """Verify register_audit_handlers() wires the correct event types."""

    def setup_method(self):
        bus.clear()

    def teardown_method(self):
        bus.clear()

    def test_registers_correct_number_of_handlers(self):
        from ee.observal_server.services.audit import register_audit_handlers

        assert bus.handler_count == 0
        register_audit_handlers()
        assert bus.handler_count == 8

    def test_registers_handlers_for_all_event_types(self):
        from ee.observal_server.services.audit import register_audit_handlers

        register_audit_handlers()
        expected_types = [
            UserCreated,
            UserDeleted,
            LoginSuccess,
            LoginFailure,
            RoleChanged,
            SettingsChanged,
            AlertRuleChanged,
            AgentLifecycleEvent,
        ]
        for event_type in expected_types:
            assert len(bus._handlers[event_type]) == 1, f"No handler registered for {event_type.__name__}"


class TestInsertAuditRow:
    """Verify _insert_audit_row constructs correct ClickHouse query."""

    @pytest.mark.asyncio
    async def test_constructs_correct_query_params(self):
        from ee.observal_server.services.audit import _insert_audit_row

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            await _insert_audit_row(
                actor_id="user-1",
                actor_email="admin@example.com",
                actor_role="admin",
                action="user.created",
                resource_type="user",
                resource_id="user-1",
                resource_name="admin@example.com",
                detail='{"is_demo": false}',
            )

        mock_query.assert_called_once()
        sql_arg = mock_query.call_args[0][0]
        params_arg = mock_query.call_args[0][1]

        assert "INSERT INTO audit_log" in sql_arg
        assert params_arg["param_aid"] == "user-1"
        assert params_arg["param_aemail"] == "admin@example.com"
        assert params_arg["param_arole"] == "admin"
        assert params_arg["param_action"] == "user.created"
        assert params_arg["param_rtype"] == "user"
        assert params_arg["param_rid"] == "user-1"
        assert params_arg["param_rname"] == "admin@example.com"
        assert params_arg["param_det"] == '{"is_demo": false}'

    @pytest.mark.asyncio
    async def test_logs_exception_on_query_failure(self):
        from ee.observal_server.services.audit import _insert_audit_row

        mock_query = AsyncMock(side_effect=RuntimeError("ClickHouse down"))
        with patch("ee.observal_server.services.audit._query", mock_query):
            # Should not raise — just logs
            await _insert_audit_row(
                actor_id="u1",
                actor_email="x@y",
                action="test",
                resource_type="test",
            )

    @pytest.mark.asyncio
    async def test_default_params_are_empty(self):
        from ee.observal_server.services.audit import _insert_audit_row

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            await _insert_audit_row(
                actor_id="u1",
                actor_email="x@y",
                action="test.action",
                resource_type="test",
            )

        params = mock_query.call_args[0][1]
        assert params["param_arole"] == ""
        assert params["param_rid"] == ""
        assert params["param_rname"] == ""
        assert params["param_hmethod"] == ""
        assert params["param_hpath"] == ""
        assert params["param_scode"] == "0"
        assert params["param_ip"] == ""
        assert params["param_ua"] == ""
        assert params["param_det"] == ""


class TestEventEmissionTriggersAudit:
    """Verify that emitting events actually calls the audit handler."""

    def setup_method(self):
        bus.clear()

    def teardown_method(self):
        bus.clear()

    @pytest.mark.asyncio
    async def test_user_created_triggers_audit(self):
        from ee.observal_server.services.audit import register_audit_handlers

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            register_audit_handlers()
            event = UserCreated(user_id="u1", email="test@example.com", role="viewer", is_demo=True)
            await bus.emit(event)

        mock_query.assert_called_once()
        params = mock_query.call_args[0][1]
        assert params["param_action"] == "user.created"
        assert params["param_aid"] == "u1"
        assert params["param_aemail"] == "test@example.com"
        assert params["param_arole"] == "viewer"
        detail = json.loads(params["param_det"])
        assert detail["is_demo"] is True

    @pytest.mark.asyncio
    async def test_login_failure_triggers_audit(self):
        from ee.observal_server.services.audit import register_audit_handlers

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            register_audit_handlers()
            event = LoginFailure(email="hacker@bad.com", method="password", reason="invalid credentials")
            await bus.emit(event)

        mock_query.assert_called_once()
        params = mock_query.call_args[0][1]
        assert params["param_action"] == "auth.login_failure"
        assert params["param_aid"] == ""
        detail = json.loads(params["param_det"])
        assert detail["reason"] == "invalid credentials"

    @pytest.mark.asyncio
    async def test_alert_rule_changed_triggers_audit(self):
        from ee.observal_server.services.audit import register_audit_handlers

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            register_audit_handlers()
            event = AlertRuleChanged(
                alert_id="alert-42",
                action="created",
                actor_id="u1",
                actor_email="admin@example.com",
            )
            await bus.emit(event)

        params = mock_query.call_args[0][1]
        assert params["param_action"] == "alert.created"
        assert params["param_rtype"] == "alert_rule"
        assert params["param_rid"] == "alert-42"

    @pytest.mark.asyncio
    async def test_agent_lifecycle_triggers_audit(self):
        from ee.observal_server.services.audit import register_audit_handlers

        mock_query = AsyncMock()
        with patch("ee.observal_server.services.audit._query", mock_query):
            register_audit_handlers()
            event = AgentLifecycleEvent(
                agent_id="agent-7",
                action="deleted",
                actor_id="u2",
                actor_email="ops@example.com",
            )
            await bus.emit(event)

        params = mock_query.call_args[0][1]
        assert params["param_action"] == "agent.deleted"
        assert params["param_rtype"] == "agent"
        assert params["param_rid"] == "agent-7"


class TestAuditLogEndpoint:
    """Test the audit log list endpoint with mocked ClickHouse responses."""

    @pytest.mark.asyncio
    async def test_list_audit_logs_returns_entries(self):
        from ee.observal_server.routes.audit import list_audit_logs

        fake_row = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-04-14 12:00:00.000",
            "actor_id": "u1",
            "actor_email": "admin@example.com",
            "actor_role": "admin",
            "action": "user.created",
            "resource_type": "user",
            "resource_id": "u2",
            "resource_name": "new@example.com",
            "http_method": "",
            "http_path": "",
            "status_code": 0,
            "ip_address": "",
            "user_agent": "",
            "detail": "{}",
        }
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = json.dumps(fake_row)

        mock_query = AsyncMock(return_value=fake_resp)
        mock_user = MagicMock()

        with patch("ee.observal_server.routes.audit._query", mock_query):
            result = await list_audit_logs(
                actor=None,
                action=None,
                resource_type=None,
                start_date=None,
                end_date=None,
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        assert len(result) == 1
        assert result[0]["action"] == "user.created"
        assert result[0]["actor_email"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_list_endpoint_handles_empty_response(self):
        from ee.observal_server.routes.audit import list_audit_logs

        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.text = ""

        mock_query = AsyncMock(return_value=fake_resp)
        mock_user = MagicMock()

        with patch("ee.observal_server.routes.audit._query", mock_query):
            result = await list_audit_logs(
                actor=None,
                action=None,
                resource_type=None,
                start_date=None,
                end_date=None,
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_list_endpoint_with_filters(self):
        from ee.observal_server.routes.audit import list_audit_logs

        fake_row = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-04-14 12:00:00.000",
            "actor_id": "u1",
            "actor_email": "admin@example.com",
            "actor_role": "admin",
            "action": "user.created",
            "resource_type": "user",
            "resource_id": "u2",
            "resource_name": "new@example.com",
            "http_method": "",
            "http_path": "",
            "status_code": 0,
            "ip_address": "",
            "user_agent": "",
            "detail": "{}",
        }
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = json.dumps(fake_row)

        mock_query = AsyncMock(return_value=fake_resp)
        mock_user = MagicMock()

        with patch("ee.observal_server.routes.audit._query", mock_query):
            result = await list_audit_logs(
                actor="admin@example.com",
                action="user.created",
                resource_type="user",
                start_date=None,
                end_date=None,
                limit=50,
                offset=0,
                current_user=mock_user,
            )

        assert len(result) == 1
        # Verify the SQL includes filter params
        sql_arg = mock_query.call_args[0][0]
        params_arg = mock_query.call_args[0][1]
        assert "actor_email = {actor:String}" in sql_arg
        assert "action = {action:String}" in sql_arg
        assert "resource_type = {rtype:String}" in sql_arg
        assert params_arg["param_actor"] == "admin@example.com"
        assert params_arg["param_action"] == "user.created"
        assert params_arg["param_rtype"] == "user"
