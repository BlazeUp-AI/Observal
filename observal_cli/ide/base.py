# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Base adapter with feature-flag gating from IDE_Registry.

Methods automatically raise NotSupportedError when the IDE lacks
the required feature in its IDE_Registry entry. Subclasses override
methods they support; the feature gate runs before the override.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from observal_cli.ide.protocol import (
    METHOD_FEATURE_MAP,
    DiscoveredMcp,
    HookSpec,
    NotSupportedError,
    ScanResult,
)


def _get_features(ide_name: str) -> set[str]:
    """Look up the feature set for an IDE from the registry."""
    from observal_cli.ide_registry import IDE_REGISTRY

    spec = IDE_REGISTRY.get(ide_name, {})
    return spec.get("features", set())


def _check_feature(ide_name: str, method_name: str) -> None:
    """Raise NotSupportedError if the IDE lacks the required feature for a method."""
    required_feature = METHOD_FEATURE_MAP.get(method_name)
    if required_feature is None:
        return  # No feature gate for this method
    features = _get_features(ide_name)
    if required_feature not in features:
        raise NotSupportedError(ide_name, method_name)


class BaseAdapter:
    """Base class providing feature-gated defaults for all protocol methods.

    On each call, checks the IDE_Registry feature set. If the IDE lacks
    the required feature, raises NotSupportedError before reaching the
    method body. Subclasses override methods they support.
    """

    @property
    def ide_name(self) -> str:
        raise NotImplementedError("Subclasses must define ide_name")

    def scan_home(self, home: Path | None = None) -> ScanResult:
        _check_feature(self.ide_name, "scan_home")
        return ScanResult()

    def scan_project(self, project_dir: Path) -> ScanResult:
        _check_feature(self.ide_name, "scan_project")
        return ScanResult()

    def get_hook_spec(self) -> HookSpec:
        _check_feature(self.ide_name, "get_hook_spec")
        return HookSpec()

    def generate_hook_config(
        self,
        observal_url: str,
        api_key: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        _check_feature(self.ide_name, "generate_hook_config")
        raise NotSupportedError(self.ide_name, "generate_hook_config")

    def detect_hooks(self, config_dir: Path) -> str:
        _check_feature(self.ide_name, "detect_hooks")
        return "none"

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        _check_feature(self.ide_name, "shim_status")
        if not mcps:
            return "none"
        from observal_cli.shared.utils import is_already_shimmed

        shimmed = sum(1 for m in mcps if m.command and is_already_shimmed({"command": m.command, "args": m.args}))
        if shimmed == 0:
            return "none"
        if shimmed == len(mcps):
            return "all"
        return "partial"
