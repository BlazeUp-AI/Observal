# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression coverage for Audit 2 tenant-scoping fixes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.routes.eval import eval_session
from api.routes.review import _apply_owner_org_filter, _owner_org_conditions
from models.mcp import McpListing
from models.user import UserRole


def _admin_user(org_id: uuid.UUID | None = None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.role = UserRole.admin
    user.org_id = org_id
    return user


@pytest.mark.asyncio
async def test_security_events_query_is_org_scoped_for_tenant_admin():
    from api.routes.admin.org import get_security_events

    org_id = uuid.uuid4()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"data": [], "rows": 0}
    mock_query = AsyncMock(return_value=fake_resp)

    with (
        patch("services.clickhouse._query", mock_query),
        patch("api.routes.admin.org.audit", AsyncMock()),
    ):
        result = await get_security_events(current_user=_admin_user(org_id))

    assert result == {"events": [], "total": 0}
    sql_arg = mock_query.call_args[0][0]
    params_arg = mock_query.call_args[0][1]
    assert "org_id = {org_id:String}" in sql_arg
    assert params_arg["param_org_id"] == str(org_id)


@pytest.mark.asyncio
async def test_audit_log_query_is_org_scoped_for_tenant_admin():
    from ee.observal_server.routes.audit import list_audit_logs

    org_id = uuid.uuid4()
    fake_resp = MagicMock(status_code=200, text="")
    mock_query = AsyncMock(return_value=fake_resp)

    with patch("ee.observal_server.routes.audit._query", mock_query):
        result = await list_audit_logs(
            actor=None,
            action=None,
            resource_type=None,
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
            current_user=_admin_user(org_id),
        )

    assert result == []
    sql_arg = mock_query.call_args[0][0]
    params_arg = mock_query.call_args[0][1]
    assert "org_id = {org_id:String}" in sql_arg
    assert params_arg["param_org_id"] == str(org_id)


@pytest.mark.asyncio
async def test_eval_session_requires_agent_before_materializing_org_scoped_session():
    materialize = AsyncMock(return_value=({"trace_id": "session-a"}, [{"type": "tool_call"}]))
    with patch("api.routes.eval.materialize_session_spans", materialize):
        with pytest.raises(HTTPException) as exc:
            await eval_session(
                "session-a",
                agent_id=None,
                db=AsyncMock(),
                current_user=_admin_user(uuid.uuid4()),
            )

    assert exc.value.status_code == 400
    materialize.assert_not_called()


@pytest.mark.asyncio
async def test_materializer_filters_otel_events_by_project_id():
    from services.hook_materializer import _fetch_session_events

    org_id = uuid.uuid4()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"data": []}
    mock_query = AsyncMock(return_value=fake_resp)

    with patch("services.hook_materializer._query", mock_query):
        events = await _fetch_session_events("session-a", project_id=str(org_id))

    assert events == []
    sql_arg = mock_query.call_args[0][0]
    params_arg = mock_query.call_args[0][1]
    assert "LogAttributes['project_id'] = {pid:String}" in sql_arg
    assert params_arg["param_pid"] == str(org_id)


def test_review_owner_org_filter_adds_tenant_condition():
    org_id = uuid.uuid4()
    stmt = _apply_owner_org_filter(select(McpListing), McpListing, org_id)

    assert _owner_org_conditions(McpListing, None) == []
    assert "owner_org_id" in str(stmt)
