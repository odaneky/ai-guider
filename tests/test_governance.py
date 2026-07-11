"""Tests for governance orchestration and Cursor integration."""

import pytest

from guider.service import GuiderService
from guider.storage.database import Database
from guider.workspace import get_active_mission_id, set_active_mission


@pytest.fixture
def service(tmp_path) -> GuiderService:
    db = Database(tmp_path / "gov.db")
    return GuiderService(db=db)


class TestClassifyTask:
    def test_trivial_task(self, service: GuiderService) -> None:
        result = service.classify_task("fix typo in readme")
        assert result["category"] == "trivial"
        assert result["requires_mission"] is False

    def test_coding_task(self, service: GuiderService) -> None:
        result = service.classify_task("build a todo webapp")
        assert result["category"] == "coding"
        assert result["requires_mission"] is True


class TestActiveMission:
    def test_set_and_get_active(self, service: GuiderService, tmp_path) -> None:
        mission = service.create_mission("Build app", set_active=False)
        workspace = str(tmp_path)
        service.set_active_mission(mission.id, workspace)
        active = service.get_active_mission(workspace)
        assert active["mission_id"] == mission.id


class TestRecordDecisionAutoResolve:
    def test_resolves_unknown_and_activates(self, service: GuiderService) -> None:
        mission = service.create_mission(
            "Build a todo webapp",
            "MVP: simple, local, no backend",
            set_active=False,
        )
        assert "Technology Stack" in mission.unknowns

        result = service.record_decision(
            mission.id,
            "Technology Stack",
            "HTML + CSS + vanilla JavaScript",
            "Simplest MVP",
        )
        updated = service.db.get_mission(mission.id)
        assert "Technology Stack" not in updated.unknowns
        assert result["resolved_unknowns"] == ["Technology Stack"]
        assert updated.confidence_score > mission.confidence_score


class TestGovernRequest:
    def test_start_phase_blocks_on_unknowns(self, service: GuiderService) -> None:
        result = service.govern_request("Build a banking application", phase="start")
        assert result["phase"] == "start"
        assert result["requires_mission"] is True
        assert result["blocked"] is True
        assert "mission_id" in result

    def test_start_skips_trivial(self, service: GuiderService) -> None:
        result = service.govern_request("fix typo in comment", phase="start")
        assert result["requires_mission"] is False
        assert result["quality_gate"] == "proceed"

    def test_act_phase_rejects_out_of_scope(self, service: GuiderService) -> None:
        mission = service.create_mission(
            "Build a todo webapp",
            "MVP: simple, local, no backend",
        )
        service.record_decision(
            mission.id,
            "Technology Stack",
            "HTML + CSS + vanilla JavaScript",
            "No framework",
        )
        service.record_decision(
            mission.id,
            "Data Storage",
            "localStorage",
            "No backend",
        )
        service.record_decision(
            mission.id,
            "Timeline",
            "Single-session MVP",
            "Minimum action",
        )

        result = service.govern_request(
            request="todo webapp",
            phase="act",
            mission_id=mission.id,
            action="Add OAuth authentication with PostgreSQL backend",
        )
        assert result["scope"]["verdict"] == "reject"
        assert result["blocked"] is True


class TestScopeWithDecisions:
    def test_rejects_postgres_after_localstorage_decision(self, service: GuiderService) -> None:
        mission = service.create_mission(
            "Build a todo webapp",
            "MVP: simple, local, no backend",
            set_active=False,
        )
        service.record_decision(
            mission.id,
            "Data Storage",
            "localStorage",
            "No backend required",
        )
        result = service.validate_scope(
            mission.id,
            "Add PostgreSQL database and OAuth authentication",
        )
        assert result["verdict"] == "reject"
        assert result["approved"] is False
