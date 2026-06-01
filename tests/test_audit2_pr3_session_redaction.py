# SPDX-FileCopyrightText: 2026 Nav-Prak <naveenprakaasam@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Session JSONL redaction regression coverage."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.secrets_redactor import REDACTED

SECRET_VALUE = "abcdef1234567890abcdef1234567890"


@pytest.mark.asyncio
async def test_session_ingest_builds_preview_and_raw_line_from_redacted_payload():
    from services.session_ingest import ingest_session_lines

    raw_line = json.dumps(
        {
            "type": "user",
            "timestamp": "2026-01-01T00:00:00.000Z",
            "uuid": "line-1",
            "message": {"content": f"please use password={SECRET_VALUE}"},
        }
    )

    with (
        patch("services.session_ingest.query_existing_for_dedup", AsyncMock(return_value=(set(), set()))),
        patch("services.session_ingest.insert_session_events", new_callable=AsyncMock) as mock_insert,
    ):
        result = await ingest_session_lines(
            session_id="session-redact",
            project_id="project-redact",
            user_id="user-redact",
            agent_id=None,
            agent_version=None,
            ide="claude-code",
            lines=[raw_line],
        )

    assert result.ingested == 1
    row = mock_insert.call_args.args[0][0]
    assert SECRET_VALUE not in row["raw_line"]
    assert SECRET_VALUE not in row["content_preview"]
    assert REDACTED in row["raw_line"]
    assert REDACTED in row["content_preview"]


@pytest.mark.asyncio
async def test_session_parse_error_logs_redacted_line_preview():
    from services.session_ingest import ingest_session_lines

    raw_line = f'{{"message": "password={SECRET_VALUE}"'

    with (
        patch("services.session_ingest.query_existing_for_dedup", AsyncMock(return_value=(set(), set()))),
        patch("services.session_ingest.insert_session_events", new_callable=AsyncMock) as mock_insert,
        patch("services.session_ingest.optic.warning") as mock_warning,
    ):
        result = await ingest_session_lines(
            session_id="session-redact",
            project_id="project-redact",
            user_id="user-redact",
            agent_id=None,
            agent_version=None,
            ide="claude-code",
            lines=[raw_line],
            start_offset=1,
        )

    assert result.errors == 1
    mock_insert.assert_not_called()
    logged_args = " ".join(str(arg) for arg in mock_warning.call_args.args)
    assert SECRET_VALUE not in logged_args
    assert REDACTED in logged_args
