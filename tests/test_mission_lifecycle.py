"""Tests for mission lifecycle."""

import pytest

from guider.mission.lifecycle import MissionLifecycle
from guider.mission.models import Mission, MissionStatus


class TestMissionLifecycle:
    def setup_method(self) -> None:
        self.lifecycle = MissionLifecycle()
        self.mission = Mission(objective="Test mission lifecycle transitions")

    def test_planning_to_active(self) -> None:
        result = self.lifecycle.activate(self.mission)
        assert result.status == MissionStatus.ACTIVE

    def test_active_to_completed(self) -> None:
        self.lifecycle.activate(self.mission)
        result = self.lifecycle.complete(self.mission)
        assert result.status == MissionStatus.COMPLETED

    def test_invalid_transition_raises(self) -> None:
        self.lifecycle.complete(self.lifecycle.activate(self.mission))
        with pytest.raises(ValueError):
            self.lifecycle.activate(self.mission)

    def test_can_transition_check(self) -> None:
        assert self.lifecycle.can_transition(self.mission, MissionStatus.ACTIVE)
        assert not self.lifecycle.can_transition(self.mission, MissionStatus.COMPLETED)
