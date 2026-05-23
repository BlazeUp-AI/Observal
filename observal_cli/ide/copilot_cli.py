# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""GitHub Copilot CLI IDE adapter (stub)."""

from __future__ import annotations

from observal_cli.ide import register_adapter
from observal_cli.ide.base import BaseAdapter


class CopilotCliAdapter(BaseAdapter):
    """Stub adapter for GitHub Copilot CLI. Not yet implemented."""

    @property
    def ide_name(self) -> str:
        return "copilot-cli"


register_adapter(CopilotCliAdapter())
