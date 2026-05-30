# SPDX-FileCopyrightText: 2026 Shreyansh Pandey <shreyanshpandey@users.noreply.github.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for MCP submit duplicate-name conflict handling.

Ensures that submitting an MCP with a name that already exists for the
same user returns a proper 409 Conflict instead of a 500 crash caused
by the CircularDependencyError in the delete+recreate pattern.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from models.mcp import McpListing


@pytest.mark.asyncio
async def test_submit_mcp_returns_409_when_duplicate_name_exists():
    """Submitting an MCP with a name the user already has returns 409."""
    from api.routes.mcp import submit_mcp
    from schemas.mcp import McpSubmitRequest

    # Mock: existing listing found with same name for this user
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = MagicMock(spec=McpListing)

    db = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)

    req = McpSubmitRequest(
        name="duplicate-test",
        version="1.0.0",
        description="Test duplicate name conflict",
        category="developer-tools",
        owner="admin",
        command="node",
        args=["index.js"],
    )

    with pytest.raises(HTTPException) as exc:
        await submit_mcp(req, MagicMock(), db, MagicMock())

    assert exc.value.status_code == 409
