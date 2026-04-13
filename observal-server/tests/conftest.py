"""Shared fixtures for JWT / auth tests."""

import hashlib
import os
import uuid

import pytest

# Override settings before any app code imports them
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")


@pytest.fixture()
def user_id():
    return str(uuid.uuid4())


@pytest.fixture()
def user_role():
    return "admin"


@pytest.fixture()
def api_key():
    """A deterministic raw API key for testing."""
    return "deadbeef" * 8


@pytest.fixture()
def api_key_hash(api_key):
    return hashlib.sha256(api_key.encode()).hexdigest()
