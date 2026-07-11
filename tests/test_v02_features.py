"""Tests for v0.2 governance features."""

import pytest

from guider.mission.models import DecisionSource
from guider.service import GuiderService
from guider.storage.database import Database


@pytest.fixture
def service(tmp_path) -> GuiderService:
    return GuiderService(db=Database(tmp_path / "v02.db"))


class TestAwaitUserInput:
    def test_creates_pending_questions(self, service: GuiderService) -> None:
        mission = service.create_mission("Build a banking app", set_active=False)
        result = service.await_user_input(mission.id)
        assert result["pending_count"] > 0
        assert result["blocked"] is True
        assert len(result["questions"]) > 0

    def test_submit_user_answer_resolves(self, service: GuiderService) -> None:
        mission = service.create_mission("Build an app", set_active=False)
        service.await_user_input(mission.id)
        unknown = mission.unknowns[0] if mission.unknowns else "Technology Stack"
        result = service.submit_user_answer(mission.id, unknown, "React + Vite")
        assert result["user_confirmed"] is True
        assert result["source"] == "user_answer"


class TestMissionTemplates:
    def test_list_templates(self, service: GuiderService) -> None:
        templates = service.list_mission_templates()
        ids = [t["id"] for t in templates]
        assert "personal-site" in ids
        assert "mvp-webapp" in ids

    def test_create_from_personal_template(self, service: GuiderService) -> None:
        result = service.create_mission_from_template(
            "personal-site",
            "Build a couple journey website",
            "Personal romantic site",
        )
        mission = result["mission"]
        assert mission["template_id"] == "personal-site"
        assert "authentication" not in [u.lower() for u in mission["unknowns"]]


class TestPivotDecision:
    def test_pivot_records_and_resets_planning(self, service: GuiderService) -> None:
        mission = service.create_mission("Build static site", set_active=False)
        service.lifecycle.activate(mission)
        service.db.save_mission(mission)
        result = service.pivot_decision(
            mission.id,
            "Migrate to Vite + React with Pinterest design",
            "User requested stack and design change",
        )
        assert result["pivot_recorded"] is True
        updated = service.db.get_mission(mission.id)
        assert updated.status.value == "planning"


class TestFileScope:
    def test_rejects_backend_paths_for_mvp(self, service: GuiderService) -> None:
        mission = service.create_mission(
            "Build MVP todo app",
            "MVP simple local",
            set_active=False,
        )
        result = service.validate_scope_with_files(
            mission.id,
            "Add backend API",
            ["backend/server.py", "backend/routes/auth.py"],
        )
        assert result["verdict"] == "reject"


class TestPreferences:
    def test_save_and_list(self, service: GuiderService) -> None:
        service.save_preference("tech_stack", "Vite + React", "User preference")
        prefs = service.list_preferences()
        assert any(p["key"] == "tech_stack" for p in prefs["preferences"])


class TestStrictMode:
    def test_rejects_agent_assumption_in_strict(self, service: GuiderService, tmp_path) -> None:
        from guider.config.loader import GuiderConfig, RulesConfig
        svc = GuiderService(db=Database(tmp_path / "strict.db"))
        mission = svc.create_mission("Build app", set_active=False)
        svc.policy_engine.config = GuiderConfig(
            profile="strict",
            rules=RulesConfig(require_user_confirmation=True),
        )
        result = svc.record_decision(
            mission.id, "Tech", "React", "assumed",
        )
        if mission.unknowns:
            assert result.get("rejected") is True


class TestGovernanceReport:
    def test_mission_report(self, service: GuiderService) -> None:
        mission = service.create_mission("Build tracker", set_active=False)
        report = service.get_governance_report(mission.id)
        assert report["mission_id"] == mission.id
        assert "governance_score" in report
        assert "compliance" in report


class TestExport:
    def test_export_creates_files(self, service: GuiderService, tmp_path) -> None:
        mission = service.create_mission("Build site", set_active=False)
        result = service.export_mission(mission.id, str(tmp_path))
        assert (tmp_path / ".ai-guider" / "mission.yaml").exists()
        assert (tmp_path / "AGENTS.md").exists()
