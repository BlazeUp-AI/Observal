# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Backend integration test for MCP duplicate name detection.

Verifies that submitting an MCP with a name that already has an approved
listing returns 409 instead of 500.

Requires: `make up` (Docker stack running on localhost:8000).

Run:
    cd observal-server
    uv run --with pytest --with pytest-asyncio --with httpx pytest ../tests/test_mcp_duplicate_name.py -v
"""

import uuid

import httpx
import pytest

BASE = "http://localhost:8000"
ADMIN_EMAIL = "admin@demo.example"
ADMIN_PASSWORD = "admin-changeme"


def _api_reachable() -> bool:
    try:
        r = httpx.get(f"{BASE}/health", timeout=2)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _api_reachable(), reason="Docker stack not running (make up)"),
]

_token_cache: str | None = None


async def _get_token() -> str:
    global _token_cache
    if _token_cache:
        return _token_cache
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        for attempt in range(3):
            r = await c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
            if r.status_code == 200:
                _token_cache = r.json()["access_token"]
                return _token_cache
            if r.status_code == 429:
                import asyncio

                await asyncio.sleep(15)
                continue
            raise AssertionError(f"Login failed: {r.text}")
    raise AssertionError("Login failed after retries (rate limited)")


@pytest.fixture()
async def admin_headers():
    token = await _get_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def client():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        yield c


class TestMcpDuplicateName:
    """Submitting an MCP with a name that already exists (approved) returns 409."""

    @pytest.fixture(autouse=True)
    def _mcp_name(self):
        self.mcp_name = f"dup-test-{uuid.uuid4().hex[:8]}"

    @pytest.mark.asyncio
    async def test_duplicate_approved_name_returns_409(self, client, admin_headers):
        payload = {
            "name": self.mcp_name,
            "version": "1.0.0",
            "description": "First submission",
            "owner": "admin",
            "category": "developer-tools",
            "git_url": "https://github.com/example/repo.git",
            "command": "node",
            "args": ["index.js"],
        }

        # Submit and approve
        r = await client.post("/api/v1/mcps/submit", headers=admin_headers, json=payload)
        assert r.status_code == 200, f"Submit failed: {r.text}"
        listing_id = str(r.json()["id"])

        r = await client.post(f"/api/v1/review/{listing_id}/approve", headers=admin_headers)
        assert r.status_code == 200, f"Approve failed: {r.text}"

        # Attempt to submit again with same name — should get 409
        payload["description"] = "Duplicate attempt"
        r = await client.post("/api/v1/mcps/submit", headers=admin_headers, json=payload)
        assert r.status_code == 409, f"Expected 409 but got {r.status_code}: {r.text}"
        assert "already" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_resubmit_pending_replaces_old(self, client, admin_headers):
        """Re-submitting a pending MCP replaces it (not a duplicate error)."""
        payload = {
            "name": self.mcp_name,
            "version": "1.0.0",
            "description": "First attempt",
            "owner": "admin",
            "category": "developer-tools",
            "git_url": "https://github.com/example/repo.git",
            "command": "node",
            "args": ["index.js"],
        }

        # Submit (stays pending)
        r = await client.post("/api/v1/mcps/submit", headers=admin_headers, json=payload)
        assert r.status_code == 200

        # Submit again — should succeed (replaces pending)
        payload["description"] = "Second attempt"
        r = await client.post("/api/v1/mcps/submit", headers=admin_headers, json=payload)
        assert r.status_code == 200
        assert r.json()["name"] == self.mcp_name
