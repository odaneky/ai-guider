"""Tests for mission builder."""

from guider.mission.builder import MissionBuilder


class TestMissionBuilder:
    def setup_method(self) -> None:
        self.builder = MissionBuilder()

    def test_build_basic_mission(self) -> None:
        mission = self.builder.build("Build a vehicle service tracker")
        assert mission.objective.startswith("Build")
        assert len(mission.success_criteria) > 0
        assert mission.status.value == "planning"

    def test_detect_unknowns_for_vague_request(self) -> None:
        mission = self.builder.build("Build a banking application")
        assert len(mission.unknowns) > 0
        unknowns_lower = [u.lower() for u in mission.unknowns]
        assert any("auth" in u or "compliance" in u for u in unknowns_lower)

    def test_confidence_decreases_with_unknowns(self) -> None:
        vague = self.builder.build("Build an app")
        specific = self.builder.build(
            "Build a Python FastAPI app with PostgreSQL and JWT auth deployed locally"
        )
        assert vague.confidence_score < specific.confidence_score

    def test_mvp_constraint(self) -> None:
        mission = self.builder.build("Build a simple MVP todo app")
        assert any("mvp" in c.lower() or "simple" in c.lower() for c in mission.constraints)

    def test_risk_detection_banking(self) -> None:
        mission = self.builder.build("Build a banking application")
        assert len(mission.risks) > 0
