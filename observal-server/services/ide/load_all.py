# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Load all IDE adapters.

Import this module to ensure all adapters are registered in the registry.
Each adapter module auto-registers itself on import.
"""

import importlib as _il

_il.import_module("services.ide.claude_code")
_il.import_module("services.ide.codex")
_il.import_module("services.ide.copilot")
_il.import_module("services.ide.copilot_cli")
_il.import_module("services.ide.cursor")
_il.import_module("services.ide.gemini_cli")
_il.import_module("services.ide.kiro")
_il.import_module("services.ide.opencode")
_il.import_module("services.ide.pi")
