# SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com>
# SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
# SPDX-FileCopyrightText: 2026 Subramania Raja <dhanpraja231@gmail.com>
# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Kaushik Kumar <kaushikrjpm10@gmail.com>
# SPDX-FileCopyrightText: 2026 Lokesh Selvam <lokeshselvam7025@gmail.com>
# SPDX-FileCopyrightText: 2026 Naraen Rammoorthi <naraen13@gmail.com>
# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-FileCopyrightText: 2026 Shreem Seth <shreemseth26@gmail.com>
# SPDX-FileCopyrightText: 2026 Vishnu Muthiah <vishnu.muthiah04@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Agent config generator — re-exports from services.ide.

All implementation has moved to services/ide/ (adapters) and
services/ide/helpers.py (shared utilities). This module exists
solely for backward compatibility with existing imports.
"""

# Re-export the orchestrator
from services.config_generator import generate_config  # noqa: F401
from services.ide import generate_agent_config, generate_all_ide_configs  # noqa: F401

# Re-export all shared helpers used by tests and other modules
from services.ide.helpers import (  # noqa: F401
    _build_hook_configs,
    _build_mcp_configs,
    _build_rules_content,
    _build_sandbox_mcp_entry,
    _build_skill_configs,
    _check_ide_compatibility,
    _claude_code_hooks_frontmatter_lines,
    _collect_hook_script_files,
    _cursor_hooks_config,
    _custom_hook_matcher_lines,
    _gemini_hooks_config,
    _generate_skill_file,
    _get_hook_events_map,
    _get_hook_scripts_dir,
    _inject_agent_id,
    _merge_hook_components_into_config,
    _model_name_to_frontmatter,
    _opencode_plugin_js,
    _sanitize_name,
    _vscode_copilot_hooks_config,
    _vscode_copilot_hooks_frontmatter_lines,
    _wrap_kiro_prompt,
)
