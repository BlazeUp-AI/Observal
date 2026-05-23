# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression coverage for Audit 2 tenant-scoping fixes."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

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


def _scalar_result(obj=None):
    result = MagicMock()
    result.scalar_one.return_value = obj
    result.scalar_one_or_none.return_value = obj
    result.scalars.return_value.all.return_value = [obj] if obj is not None else []
    result.all.return_value = []
    return result


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
async def test_eval_session_rejects_materialized_session_from_another_org():
    org_id = uuid.uuid4()
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "tenant-agent"
    agent.owner_org_id = org_id

    materialize = AsyncMock(
        return_value=(
            {"trace_id": "session-a", "project_id": str(uuid.uuid4())},
            [{"type": "tool_call", "name": "Read", "status": "success"}],
        )
    )

    with (
        patch("api.routes.eval.resolve_prefix_id", AsyncMock(return_value=agent)),
        patch("api.routes.eval.materialize_session_spans", materialize),
    ):
        with pytest.raises(HTTPException) as exc:
            await eval_session(
                "session-a",
                agent_id=str(agent.id),
                db=AsyncMock(),
                current_user=_admin_user(org_id),
            )

    assert exc.value.status_code == 404
    materialize.assert_awaited_once_with("session-a", project_id=str(org_id))


@pytest.mark.asyncio
async def test_run_evaluation_scopes_trace_fetch_and_span_query_to_org():
    from api.routes.eval import run_evaluation

    org_id = uuid.uuid4()
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "tenant-agent"
    agent.owner_org_id = org_id

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(MagicMock()))

    fetch = AsyncMock(return_value=[{"trace_id": "trace-1"}])
    query_spans = AsyncMock(return_value=[{"type": "tool_call", "name": "Read", "status": "success"}])

    with (
        patch("api.routes.eval.resolve_prefix_id", AsyncMock(return_value=agent)),
        patch("api.routes.eval.fetch_traces", fetch),
        patch("api.routes.eval.query_spans", query_spans),
        patch("api.routes.eval.run_structured_eval", AsyncMock(return_value=MagicMock())),
        patch("api.routes.eval.audit", AsyncMock()),
        patch("api.routes.eval.EvalRunDetailResponse.model_validate", MagicMock(return_value={"ok": True})),
    ):
        result = await run_evaluation(
            str(agent.id),
            req=None,
            db=db,
            current_user=_admin_user(org_id),
        )

    assert result == {"ok": True}
    fetch.assert_awaited_once_with(str(agent.id), trace_id=None, project_id=str(org_id))
    query_spans.assert_awaited_once_with(str(org_id), "trace-1", limit=500)


@pytest.mark.asyncio
async def test_eval_agent_in_session_scopes_name_and_id_materialization_to_org():
    from api.routes.eval import eval_agent_in_session

    org_id = uuid.uuid4()
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "tenant-agent"
    agent.owner_org_id = org_id

    materialize = AsyncMock(
        side_effect=[
            ({"trace_id": "session-a", "agent_id": ""}, [{"type": "tool_call"}], None),
            ({"trace_id": "session-a", "agent_id": ""}, [{"type": "tool_call"}], None),
        ]
    )

    with (
        patch("api.routes.agent.helpers._load_agent", AsyncMock(return_value=agent)),
        patch("api.routes.eval.materialize_agent_eval", materialize),
    ):
        with pytest.raises(HTTPException) as exc:
            await eval_agent_in_session(
                str(agent.id),
                "session-a",
                db=AsyncMock(),
                current_user=_admin_user(org_id),
            )

    assert exc.value.status_code == 404
    assert materialize.await_args_list == [
        call("session-a", agent.name, project_id=str(org_id)),
        call("session-a", str(agent.id), project_id=str(org_id)),
    ]


@pytest.mark.asyncio
async def test_list_agent_evaluated_sessions_filters_clickhouse_by_project_id():
    from api.routes.eval import list_agent_evaluated_sessions

    org_id = uuid.uuid4()
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "tenant-agent"
    agent.owner_org_id = org_id

    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {
        "data": [
            {
                "session_id": "session-a",
                "start_time": "2026-01-01 00:00:00",
                "end_time": "2026-01-01 00:00:01",
                "event_count": 2,
                "first_prompt": "hello",
                "service_name": "kiro-cli",
            }
        ]
    }
    mock_query = AsyncMock(return_value=fake_resp)

    with (
        patch("api.routes.eval.resolve_prefix_id", AsyncMock(return_value=agent)),
        patch("api.routes.eval._query", mock_query),
        patch("api.routes.eval.audit", AsyncMock()),
    ):
        result = await list_agent_evaluated_sessions(
            str(agent.id),
            db=AsyncMock(),
            current_user=_admin_user(org_id),
        )

    assert result[0]["session_id"] == "session-a"
    sql_arg = mock_query.call_args[0][0]
    params_arg = mock_query.call_args[0][1]
    assert "LogAttributes['project_id'] = {project_id:String}" in sql_arg
    assert params_arg["param_project_id"] == str(org_id)


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


@pytest.mark.asyncio
async def test_materialize_session_spans_passes_project_id_and_preserves_trace_org_fields():
    from services.hook_materializer import materialize_session_spans

    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    fetch = AsyncMock(
        return_value=[
            {
                "timestamp": "2026-01-01 00:00:00.000",
                "event_name": "hook_Stop",
                "body": "done",
                "attributes": {
                    "event.name": "hook_Stop",
                    "project_id": org_id,
                    "user.id": user_id,
                    "agent_name": "tenant-agent",
                    "tool_response": "done",
                },
                "service_name": "kiro-cli",
            }
        ]
    )

    with patch("services.hook_materializer._fetch_session_events", fetch):
        trace, spans = await materialize_session_spans("session-a", project_id=org_id)

    fetch.assert_awaited_once_with("session-a", project_id=org_id)
    assert trace["project_id"] == org_id
    assert trace["user_id"] == user_id
    assert spans[0]["type"] == "agent_response"


@pytest.mark.asyncio
async def test_materialize_agent_eval_passes_project_id_and_finds_agent_context():
    from services.hook_materializer import materialize_agent_eval

    org_id = str(uuid.uuid4())
    fetch = AsyncMock(
        return_value=[
            {
                "timestamp": "2026-01-01 00:00:00.000",
                "event_name": "hook_SubagentStart",
                "body": "review this",
                "attributes": {
                    "event.name": "hook_SubagentStart",
                    "project_id": org_id,
                    "agent_type": "security-auditor",
                    "tool_input": "review this",
                },
                "service_name": "claude-code",
            },
            {
                "timestamp": "2026-01-01 00:00:01.000",
                "event_name": "hook_SubagentStop",
                "body": "looks safe",
                "attributes": {
                    "event.name": "hook_SubagentStop",
                    "project_id": org_id,
                    "agent_type": "security-auditor",
                    "tool_response": "looks safe",
                },
                "service_name": "claude-code",
            },
        ]
    )

    with patch("services.hook_materializer._fetch_session_events", fetch):
        trace, spans, ctx = await materialize_agent_eval(
            "session-a",
            "security-auditor",
            project_id=org_id,
        )

    fetch.assert_awaited_once_with("session-a", project_id=org_id)
    assert trace["project_id"] == org_id
    assert len(spans) == 2
    assert ctx is not None
    assert ctx.delegation_prompt == "review this"


def test_review_owner_org_filter_adds_tenant_condition():
    org_id = uuid.uuid4()
    stmt = _apply_owner_org_filter(select(McpListing), McpListing, org_id)

    assert _owner_org_conditions(McpListing, None) == []
    assert "owner_org_id" in str(stmt)


@pytest.mark.asyncio
async def test_find_listing_passes_org_conditions_to_prefix_and_name_lookup():
    from api.routes.review import _find_listing

    org_id = uuid.uuid4()
    listing = MagicMock()
    listing.id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(listing))
    seen_conditions = []

    async def fake_resolve(*args, **kwargs):
        seen_conditions.append(kwargs.get("extra_conditions"))
        raise HTTPException(status_code=404, detail="not found")

    with patch("api.routes.review.resolve_prefix_id", AsyncMock(side_effect=fake_resolve)):
        listing_type, found = await _find_listing("tenant-mcp", db, org_id)

    assert listing_type == "mcp"
    assert found is listing
    assert any(seen_conditions)
    assert "owner_org_id" in str(db.execute.call_args[0][0])


@pytest.mark.asyncio
async def test_check_agent_components_ready_blocks_components_outside_org():
    from api.routes.review import _check_agent_components_ready

    comp = MagicMock()
    comp.component_type = "mcp"
    comp.component_id = uuid.uuid4()

    empty_rows = MagicMock()
    empty_rows.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=empty_rows)

    ready, blocking = await _check_agent_components_ready([comp], db, uuid.uuid4())

    assert ready is False
    assert blocking == [
        {
            "component_type": "mcp",
            "component_id": str(comp.component_id),
            "name": "",
            "status": "not_found_or_not_in_org",
        }
    ]
    assert "owner_org_id" in str(db.execute.call_args[0][0])


@pytest.mark.asyncio
async def test_bundle_belongs_to_org_requires_submitter_membership():
    from api.routes.review import _bundle_belongs_to_org

    bundle = MagicMock()
    bundle.submitted_by = uuid.uuid4()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(None))

    assert await _bundle_belongs_to_org(bundle, db, None) is True
    assert await _bundle_belongs_to_org(bundle, db, uuid.uuid4()) is False
    assert "org_id" in str(db.execute.call_args[0][0])


@pytest.mark.asyncio
async def test_fetch_traces_includes_project_filter_for_recent_and_single_trace_queries():
    from services.eval.eval_service import fetch_traces

    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {"data": [{"trace_id": "trace-1"}]}
    mock_query = AsyncMock(return_value=fake_resp)

    with patch("services.eval.eval_service._query", mock_query):
        rows = await fetch_traces("agent-a", limit=5, project_id="org-a")
        single = await fetch_traces("agent-a", trace_id="trace-1", project_id="org-a")

    assert rows == [{"trace_id": "trace-1"}]
    assert single == [{"trace_id": "trace-1"}]

    recent_sql, recent_params = mock_query.await_args_list[0].args
    single_sql, single_params = mock_query.await_args_list[1].args
    assert "project_id = {pid:String}" in recent_sql
    assert "LIMIT 5" in recent_sql
    assert recent_params["param_pid"] == "org-a"
    assert "trace_id = {tid:String}" in single_sql
    assert "project_id = {pid:String}" in single_sql
    assert single_params["param_tid"] == "trace-1"
    assert single_params["param_pid"] == "org-a"


@pytest.mark.asyncio
async def test_emit_security_event_resolves_org_id_before_clickhouse_insert():
    from services.security_events import EventType, SecurityEvent, Severity, emit_security_event

    event = SecurityEvent(
        event_type=EventType.PERMISSION_DENIED,
        severity=Severity.WARNING,
        outcome="failure",
        actor_id=str(uuid.uuid4()),
    )
    mock_query = AsyncMock()

    with (
        patch("services.security_events._resolve_actor_org_id", AsyncMock(return_value="org-a")),
        patch("services.clickhouse._query", mock_query),
    ):
        await emit_security_event(event)

    assert event.org_id == "org-a"
    inserted = json.loads(mock_query.call_args.kwargs["data"])
    assert inserted["org_id"] == "org-a"


@pytest.mark.asyncio
async def test_resolve_actor_org_id_reads_database_once_and_caches_result():
    import services.security_events as security_events

    security_events._ACTOR_ORG_CACHE.clear()
    actor_id = str(uuid.uuid4())
    org_id = uuid.uuid4()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = org_id
    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)

    class FakeSession:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch("database.async_session", MagicMock(return_value=FakeSession())):
        first = await security_events._resolve_actor_org_id(actor_id)
        second = await security_events._resolve_actor_org_id(actor_id)

    assert first == str(org_id)
    assert second == str(org_id)
    db.execute.assert_awaited_once()
