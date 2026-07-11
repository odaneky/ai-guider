from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Type

from guider.mission.models import Mission, ValidatorResult

ValidatorFn = Callable[..., ValidatorResult]


class GuiderPlugin(ABC):
    """Base class for domain-specific guidance plugins."""

    name: str = "base"
    description: str = "Base plugin"

    @abstractmethod
    def register_validators(self) -> Dict[str, ValidatorFn]:
        """Return a mapping of validator name to callable."""

    def on_mission_created(self, mission: Mission) -> None:
        """Hook called after mission creation."""

    def on_decision_recorded(self, mission: Mission, title: str) -> None:
        """Hook called after a decision is recorded."""


class PluginRegistry:
    """Registry for loaded plugins and their validators."""

    def __init__(self) -> None:
        self._plugins: Dict[str, GuiderPlugin] = {}
        self._validators: Dict[str, ValidatorFn] = {}

    def register(self, plugin: GuiderPlugin) -> None:
        self._plugins[plugin.name] = plugin
        self._validators.update(plugin.register_validators())

    def get_plugin(self, name: str) -> Optional[GuiderPlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    def get_validator(self, name: str) -> Optional[ValidatorFn]:
        return self._validators.get(name)

    def list_validators(self) -> List[str]:
        return list(self._validators.keys())

    def run_validator(self, name: str, *args, **kwargs) -> Optional[ValidatorResult]:
        validator = self.get_validator(name)
        if validator:
            return validator(*args, **kwargs)
        return None


_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
