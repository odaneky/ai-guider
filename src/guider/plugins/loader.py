from __future__ import annotations

import importlib
import pkgutil
from typing import List, Optional

from guider.config.loader import get_config
from guider.plugins.base import GuiderPlugin, PluginRegistry, get_registry
from guider.plugins.software_engineering import SoftwareEngineeringPlugin


BUILTIN_PLUGINS = [
    SoftwareEngineeringPlugin,
]
try:
    from guider.plugins.personal import PersonalSitePlugin
    BUILTIN_PLUGINS.append(PersonalSitePlugin)
except ImportError:
    pass


def load_plugins(plugin_names: Optional[List[str]] = None) -> PluginRegistry:
    registry = get_registry()

    for plugin_cls in BUILTIN_PLUGINS:
        plugin = plugin_cls()
        if plugin.name not in registry.list_plugins():
            registry.register(plugin)

    config = get_config()
    names = plugin_names or config.plugins

    # Explicit class map for modules whose class name != TitleCase(module)Plugin
    CLASS_ALIASES = {
        "personal": "PersonalSitePlugin",
        "software_engineering": "SoftwareEngineeringPlugin",
    }

    for name in names:
        if name in registry.list_plugins():
            continue
        try:
            module = importlib.import_module(f"guider.plugins.{name}")
            class_name = CLASS_ALIASES.get(
                name, f"{name.title().replace('_', '')}Plugin"
            )
            plugin_cls = getattr(module, class_name, None)
            if plugin_cls is None:
                # Fallback: first GuiderPlugin subclass in module
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, GuiderPlugin)
                        and obj is not GuiderPlugin
                    ):
                        plugin_cls = obj
                        break
            if plugin_cls and issubclass(plugin_cls, GuiderPlugin):
                registry.register(plugin_cls())
        except (ImportError, AttributeError):
            continue

    return registry
