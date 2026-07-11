"""Tests for SQLite storage."""

from guider.mission.models import Decision, Mission, MissionEvent, MissionEventType
from guider.storage.database import Database


class TestDatabase:
    def test_save_and_get_mission(self, temp_db: Database) -> None:
        mission = Mission(objective="Test storage roundtrip")
        temp_db.save_mission(mission)
        loaded = temp_db.get_mission(mission.id)
        assert loaded is not None
        assert loaded.objective == mission.objective

    def test_list_missions(self, temp_db: Database) -> None:
        for i in range(3):
            temp_db.save_mission(Mission(objective=f"Mission {i}"))
        missions = temp_db.list_missions()
        assert len(missions) == 3

    def test_record_event(self, temp_db: Database) -> None:
        mission = Mission(objective="Event test")
        temp_db.save_mission(mission)
        event = MissionEvent(
            mission_id=mission.id,
            event_type=MissionEventType.CREATED,
            message="Created",
        )
        temp_db.record_event(event)
        events = temp_db.list_events(mission.id)
        assert len(events) == 1

    def test_save_decision(self, temp_db: Database) -> None:
        mission = Mission(objective="Decision test")
        temp_db.save_mission(mission)
        decision = Decision(
            mission_id=mission.id,
            title="Database",
            description="PostgreSQL",
            reason="Relational model",
        )
        temp_db.save_decision(decision)
        decisions = temp_db.list_decisions(mission.id)
        assert len(decisions) == 1
        assert decisions[0].title == "Database"

    def test_stats(self, temp_db: Database) -> None:
        temp_db.save_mission(Mission(objective="Stats test"))
        stats = temp_db.get_stats()
        assert stats["missions"] == 1
