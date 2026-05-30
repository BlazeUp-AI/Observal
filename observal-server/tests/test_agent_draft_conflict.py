# SPDX-FileCopyrightText: 2026 Shreyansh Pandey <shreyanshpandey@users.noreply.github.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for agent draft duplicate-name conflict handling.

Ensures that saving an agent draft with a name that already exists for
the same user returns a proper 409 Conflict instead of an unhandled 500
IntegrityError crash.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.routes.agent.draft import save_draft
from schemas.agent import AgentCreateRequest


@pytest.mark.asyncio
async def test_save_draft_returns_409_when_duplicate_name_exists():
    """Saving an agent draft with a name the user already has returns 409."""

    # Mock: existing agent found with same name for this user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)

    req = AgentCreateRequest(
        name="duplicate-agent",
        version="1.0.0",
        description="Test agent draft conflict",
        owner="admin",
        model_name="gpt-4",
        prompt="You are a test agent",
    )

    with pytest.raises(HTTPException) as exc:
        await save_draft(req, db, MagicMock())

    assert exc.value.status_code == 409
