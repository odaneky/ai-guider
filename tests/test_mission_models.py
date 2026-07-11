"""Tests for mission models."""

from guider.mission.models import Mission, MissionStatus, ValidatorResult


class TestMissionModels:
    def test_mission_defaults(self) -> None:
        mission = Mission(objective="Test objective for validation")
        assert mission.id.startswith("mission-")
        assert mission.status == MissionStatus.PLANNING
        assert mission.confidence_score == 0.5

    def test_validator_result_bounds(self) -> None:
        result = ValidatorResult(name="test", score=95, passed=True, reason="ok")
        assert result.score == 95

    def test_mission_serialization(self) -> None:
        mission = Mission(
            objective="Build tracker",
            success_criteria=["Users can create vehicles"],
            unknowns=["Authentication"],
        )
        data = mission.model_dump()
        assert data["objective"] == "Build tracker"
        assert "Authentication" in data["unknowns"]
