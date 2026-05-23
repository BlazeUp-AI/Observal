# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Gemini CLI IDE adapter (stub)."""

from __future__ import annotations

from observal_cli.ide import register_adapter
from observal_cli.ide.base import BaseAdapter


class GeminiCliAdapter(BaseAdapter):
    """Stub adapter for Gemini CLI (Google). Not yet implemented."""

    @property
    def ide_name(self) -> str:
        return "gemini-cli"


register_adapter(GeminiCliAdapter())
