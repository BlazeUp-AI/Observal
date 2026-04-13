"""Enterprise configuration validator.

Checks that required settings are properly configured for enterprise mode.
Returns a list of human-readable issue descriptions (empty = healthy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Settings


def validate_enterprise_config(settings: Settings) -> list[str]:
    """Validate enterprise-required configuration.  Returns list of issues."""
    issues: list[str] = []

    if settings.SECRET_KEY == "change-me-to-a-random-string":
        issues.append("SECRET_KEY is using default value")

    if not settings.OAUTH_CLIENT_ID:
        issues.append("OAUTH_CLIENT_ID is not set")

    if not settings.OAUTH_CLIENT_SECRET:
        issues.append("OAUTH_CLIENT_SECRET is not set")

    if not settings.OAUTH_SERVER_METADATA_URL:
        issues.append("OAUTH_SERVER_METADATA_URL is not set")

    if settings.FRONTEND_URL in ("http://localhost:3000", ""):
        issues.append("FRONTEND_URL is localhost or empty")

    return issues
