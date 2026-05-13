# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Redact secrets from text before sending it to a third-party LLM provider.

Keeps this module dependency-free so it can be imported anywhere early
in startup without pulling in heavy optional packages.

Usage
-----
from services.secret_redactor import sanitize_for_provider

prompt = sanitize_for_provider(raw_text)

What it redacts
---------------
- JWT tokens  (eyJ…)
- Bearer / Authorization header values
- Embedded URL credentials  (scheme://user:password@host)
- key=value assignments for common secret field names
- PEM private-key blocks
- Long hex strings that look like tokens / hashes  (≥ 32 hex chars)

What it does NOT do
-------------------
- It does not remove prompt-injection vectors — use TraceSanitizer for that.
- It is not a complete DLP solution; it covers the most common patterns.
"""

import re

# ── Patterns ─────────────────────────────────────────────────────────────────

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # JWT  (header.payload.signature, each part ≥ 4 chars of base64url)
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}"),
        "[REDACTED_JWT]",
    ),
    # Authorization / Bearer header values
    (
        re.compile(r"((?:Bearer|Token|Authorization)\s+)[A-Za-z0-9_\-\.]{16,}", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # URL-embedded credentials  scheme://user:password@host
    (
        re.compile(r"([a-z][a-z0-9+\-.]*://[^:/\s@]{1,64}:)[^@\s]{1,256}(@)", re.IGNORECASE),
        r"\1[REDACTED]\2",
    ),
    # key=value / key: value for common secret field names
    (
        re.compile(
            r"(?P<key>(?:password|passwd|secret|api[_-]?key|access[_-]?token"
            r"|auth[_-]?token|private[_-]?key|client[_-]?secret|x-api-key)"
            r"\s*[=:]\s*)(?P<val>[^\s,\]{}\"\';\n]{6,})",
            re.IGNORECASE,
        ),
        r"\g<key>[REDACTED]",
    ),
    # PEM private-key blocks
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE[A-Z ]*KEY-----[\s\S]{0,4096}?-----END [A-Z ]*PRIVATE[A-Z ]*KEY-----"),
        "[REDACTED_PEM]",
    ),
    # Long hex strings (≥ 32 chars) — tokens, hashes, API keys
    (
        re.compile(r"\b[0-9a-fA-F]{32,}\b"),
        "[REDACTED_HEX]",
    ),
]


# ── Public API ────────────────────────────────────────────────────────────────


def sanitize_for_provider(text: str) -> str:
    """Return *text* with secrets redacted.

    Safe to call on non-string values — they are returned unchanged.
    Compose with ``TraceSanitizer.sanitize_for_judge()`` for full protection:

    - ``sanitize_for_judge``  strips prompt-injection vectors
    - ``sanitize_for_provider``  strips credential leakage
    """
    if not isinstance(text, str):
        return text  # type: ignore[return-value]
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
