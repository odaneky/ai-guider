"""Tests for mission tracker."""

from guider.mission.models import Mission
from guider.mission.tracker import MissionTracker


class TestMissionTracker:
    def setup_method(self) -> None:
        self.tracker = MissionTracker()
        self.mission = Mission(
            objective="Build a tracker",
            success_criteria=["Create items", "Track history"],
            unknowns=["Database"],
        )

    def test_progress_calculation(self) -> None:
        progress = self.tracker.get_progress(self.mission)
        assert progress["success_criteria_total"] == 2
        assert progress["success_criteria_completed"] == 0
        assert progress["unknowns_remaining"] == 1

    def test_mark_criterion_complete(self) -> None:
        self.tracker.mark_criterion_complete(self.mission, "Create items")
        assert "Create items" in self.mission.completed_items
        progress = self.tracker.get_progress(self.mission)
        assert progress["success_criteria_completed"] == 1

    def test_resolve_unknown(self) -> None:
        original_confidence = self.mission.confidence_score
        self.tracker.resolve_unknown(self.mission, "Database")
        assert "Database" not in self.mission.unknowns
        # Confidence boost is owned by GuiderService, not the tracker
        assert self.mission.confidence_score == original_confidence

    def test_state_summary(self) -> None:
        state = self.tracker.get_state_summary(self.mission)
        assert state["objective"] == "Build a tracker"
        assert "success_criteria" in state
