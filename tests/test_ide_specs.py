# SPDX-FileCopyrightText: 2026 Observal contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from observal_cli.ide_specs import claude_code_hooks_spec as claude_spec
from observal_cli.ide_specs import kiro_hooks_spec as kiro_spec


def _claude_hook_commands() -> list[str]:
    desired_hooks = claude_spec.get_desired_hooks()
    return [
        hook["command"]
        for event_groups in desired_hooks.values()
        for group in event_groups
        for hook in group["hooks"]
    ]


def test_claude_desired_hooks_include_user_prompt_and_stop_events():
    desired_hooks = claude_spec.get_desired_hooks()

    assert set(desired_hooks) == {"UserPromptSubmit", "Stop"}


def test_claude_desired_hooks_attach_observal_metadata_to_each_group():
    desired_hooks = claude_spec.get_desired_hooks()

    for event_groups in desired_hooks.values():
        for group in event_groups:
            assert group[claude_spec.OBSERVAL_METADATA_KEY] == {
                "version": claude_spec.HOOKS_SPEC_VERSION
            }


def test_claude_desired_hooks_use_session_push_command():
    commands = _claude_hook_commands()

    assert commands
    assert all("observal_cli.hooks.session_push" in command for command in commands)


def test_claude_hook_entry_matches_current_session_push_path():
    assert claude_spec.is_observal_hook_entry(
        {"command": "python -m observal_cli.hooks.session_push"}
    )


def test_claude_hook_entry_matches_every_legacy_marker_in_command():
    for marker in claude_spec._LEGACY_HOOK_MARKERS:
        assert claude_spec.is_observal_hook_entry({"command": f"python -m {marker}"})


def test_claude_hook_entry_matches_legacy_marker_in_url():
    assert claude_spec.is_observal_hook_entry({"url": "https://api.example/api/v1/otel/hooks"})


def test_claude_hook_entry_rejects_foreign_command_and_url():
    assert not claude_spec.is_observal_hook_entry(
        {
            "command": "python -m other_tool.hooks.push",
            "url": "https://api.example/hooks",
        }
    )


def test_claude_matcher_group_matches_via_metadata_key():
    assert claude_spec.is_observal_matcher_group({claude_spec.OBSERVAL_METADATA_KEY: {}})


def test_claude_matcher_group_matches_via_legacy_hook_command():
    assert claude_spec.is_observal_matcher_group(
        {"hooks": [{"command": "python -m observal_cli.hooks.buffer_event"}]}
    )


def test_claude_matcher_group_rejects_foreign_hooks():
    assert not claude_spec.is_observal_matcher_group(
        {"hooks": [{"command": "python -m other_tool.hooks.push"}]}
    )


def test_kiro_hooks_return_expected_event_keys():
    hooks = kiro_spec.build_kiro_hooks()

    assert set(hooks) == {"userPromptSubmit", "stop"}


def test_kiro_hooks_use_session_push_command_for_each_event():
    hooks = kiro_spec.build_kiro_hooks()

    for event_hooks in hooks.values():
        assert event_hooks == [{"command": event_hooks[0]["command"]}]
        assert "observal_cli.hooks.kiro_session_push" in event_hooks[0]["command"]


def test_hooks_spec_version_is_string_and_matches_metadata_policy():
    assert isinstance(claude_spec.HOOKS_SPEC_VERSION, str)
    assert claude_spec.HOOKS_SPEC_VERSION

    desired_hooks = claude_spec.get_desired_hooks()
    metadata_versions = {
        group[claude_spec.OBSERVAL_METADATA_KEY]["version"]
        for event_groups in desired_hooks.values()
        for group in event_groups
    }
    assert metadata_versions == {claude_spec.HOOKS_SPEC_VERSION}
