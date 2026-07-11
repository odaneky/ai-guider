"""Tests for plugins."""

from guider.mission.models import Mission
from guider.plugins.loader import load_plugins
from guider.plugins.software_engineering import SoftwareEngineeringPlugin


class TestPlugins:
    def test_software_engineering_plugin_registers_validators(self) -> None:
        plugin = SoftwareEngineeringPlugin()
        validators = plugin.register_validators()
        assert "review_code_change" in validators
        assert "detect_architecture_issue" in validators
        assert "check_tests" in validators

    def test_review_code_change_mvp_refactor(self) -> None:
        plugin = SoftwareEngineeringPlugin()
        mission = Mission(
            objective="Build MVP",
            constraints=["Keep MVP simple"],
        )
        result = plugin.review_code_change(mission, "Refactor entire module structure")
        assert result.score < 85

    def test_load_plugins_builtin(self) -> None:
        registry = load_plugins()
        assert "software_engineering" in registry.list_plugins()
        assert len(registry.list_validators()) >= 3
