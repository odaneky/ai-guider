"""Tests for GuiderService."""

from guider.service import GuiderService
from guider.storage.database import Database


class TestGuiderService:
    def setup_method(self) -> None:
        self.db = Database.__new__(Database)
        # Use temp db via fixture pattern
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.service = GuiderService(db=self.db)

    def teardown_method(self) -> None:
        self.tmp.cleanup()

    def test_create_mission(self) -> None:
        mission = self.service.create_mission("Build a vehicle tracker", "MVP project")
        assert mission.id
        loaded = self.db.get_mission(mission.id)
        assert loaded is not None

    def test_analyze_unknowns(self) -> None:
        result = self.service.analyze_unknowns("Build a banking app")
        assert result["count"] > 0
        assert "recommended_questions" in result["unknowns"][0]

    def test_validate_scope(self) -> None:
        mission = self.service.create_mission("Build a todo app")
        result = self.service.validate_scope(mission.id, "Add todo creation form")
        assert "approved" in result
        assert "verdict" in result
        assert "confidence" in result

    def test_detect_assumptions(self) -> None:
        result = self.service.detect_assumptions("We will use React for the frontend")
        assert result["count"] >= 0

    def test_review_plan(self) -> None:
        mission = self.service.create_mission("Build an API")
        result = self.service.review_plan(
            mission.id, ["Design schema", "Implement endpoints", "Write tests"]
        )
        assert "approved" in result
        assert "score" in result

    def test_validate_completion(self) -> None:
        mission = self.service.create_mission("Build tracker")
        result = self.service.validate_completion(mission.id)
        assert result["complete"] is False
        assert len(result["missing_items"]) > 0

    def test_record_decision(self) -> None:
        mission = self.service.create_mission("Build app")
        result = self.service.record_decision(
            mission.id, "Database", "PostgreSQL", "Relational data model"
        )
        assert result["title"] == "Database"

    def test_get_mission_state(self) -> None:
        mission = self.service.create_mission("Build service")
        state = self.service.get_mission_state(mission.id)
        assert state["mission_id"] == mission.id
        assert "policy" in state
