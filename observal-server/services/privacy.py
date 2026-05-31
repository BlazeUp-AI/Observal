# SPDX-FileCopyrightText: 2026 Nav-Prak <naveenprakaasam@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Organization ingest privacy modes (data minimization at ingest).

Secret redaction is always applied regardless of mode (see
``services.secrets_redactor``). The privacy mode only controls how much raw
payload content is retained:

- ``full``          - retain payloads (input/output/error/raw_line) + metadata/tags.
- ``redacted``      - retain metadata/tags; replace free-text payloads with short
                      redacted previews.
- ``metadata_only`` - drop free-text payloads entirely; retain metadata/tags.
- ``disabled_raw``  - drop payloads and metadata/tags; keep only metrics/identifiers.
"""

from __future__ import annotations

from typing import Any

from services.secrets_redactor import redact_secrets, redact_value

PRIVACY_MODE_FULL = "full"
PRIVACY_MODE_REDACTED = "redacted"
PRIVACY_MODE_METADATA_ONLY = "metadata_only"
PRIVACY_MODE_DISABLED_RAW = "disabled_raw"

PRIVACY_MODES = (
    PRIVACY_MODE_FULL,
    PRIVACY_MODE_REDACTED,
    PRIVACY_MODE_METADATA_ONLY,
    PRIVACY_MODE_DISABLED_RAW,
)

DEFAULT_PRIVACY_MODE = PRIVACY_MODE_FULL


def normalize_privacy_mode(mode: str | None) -> str:
    """Coerce an arbitrary value to a known privacy mode, defaulting to ``full``."""
    if isinstance(mode, str) and mode in PRIVACY_MODES:
        return mode
    return DEFAULT_PRIVACY_MODE


# Length cap for the short redacted previews kept under the ``redacted`` mode.
PREVIEW_LEN = 256


def redact_payload_text(value: str | None, mode: str) -> str | None:
    """Apply secret redaction and the mode's retention policy to a free-text payload.

    ``full`` keeps the (secret-redacted) value, ``redacted`` keeps a short
    redacted preview, and ``metadata_only``/``disabled_raw`` drop it entirely.
    ``None`` (absent) is preserved.
    """
    if value is None:
        return value
    if mode in (PRIVACY_MODE_METADATA_ONLY, PRIVACY_MODE_DISABLED_RAW):
        return ""
    redacted = redact_secrets(value)
    if mode == PRIVACY_MODE_REDACTED:
        return redacted[:PREVIEW_LEN]
    return redacted


def redact_structured(value: Any, mode: str) -> Any:
    """Apply the mode's retention policy to structured metadata/tags.

    All modes except ``disabled_raw`` keep the value (recursively redacted);
    ``disabled_raw`` drops it (empty container, preserving its type).
    """
    if value is None:
        return value
    if mode == PRIVACY_MODE_DISABLED_RAW:
        if isinstance(value, dict):
            return {}
        if isinstance(value, list):
            return []
        if isinstance(value, tuple):
            return ()
        return value
    return redact_value(value)
