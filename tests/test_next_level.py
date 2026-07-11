"""Phase 1–3 lifecycle, classifier, refine_plan, and E2E completion tests."""

import pytest

from guider.mission.classifier import classify_task, objectives_similar
from guider.mission.models import DecisionSource, MissionStatus
from guider.service import GuiderService
from guider.storage.database import Database


@pytest.fixture
def service(tmp_path) -> GuiderService:
    return GuiderService(db=Database(tmp_path / "next.db"))


class TestClassifier:
    def test_oauth_requires_mission(self) -> None:
        result = classify_task("add oauth login")
        assert result["requires_mission"] is True
        assert result["category"] != "trivial"

    def test_payment_design_requires_mission(self) -> None:
        result = classify_task("design payment system")
        assert result["requires_mission"] is True

    def test_typo_still_trivial(self) -> None:
        result = classify_task("fix typo in readme")
        assert result["category"] == "trivial"
        assert result["requires_mission"] is False


class TestConfidenceSingleBoost:
    def test_one_user_answer_one_boost(self, service: GuiderService) -> None:
        mission = service.create_mission(
            "Build a todo webapp",
            "MVP local",
            set_active=False,
        )
        before = mission.confidence_score
        # Resolve exactly one unknown via user answer path
        unknown = mission.unknowns[0]
        service.submit_user_answer(mission.id, unknown, "User choice")
        after = service.db.get_mission(mission.id)
        # Only decision boost (+0.08), not tracker + decision
        delta = round(after.confidence_score - before, 2)
        assert delta == pytest.approx(0.08, abs=0.001)


class TestIdempotentStart:
    def test_reuses_active_mission(self, service: GuiderService, tmp_path) -> None:
        ws = str(tmp_path / "proj")
        first = service.govern_request(
            "Build a personal website for our journey",
            phase="start",
            workspace_path=ws,
        )
        second = service.govern_request(
            "Build a personal website for our journey",
            phase="start",
            workspace_path=ws,
        )
        assert first["mission_id"] == second["mission_id"]
        assert second.get("resumed") is True


class TestCompletionPath:
    def test_e2e_to_completed(self, service: GuiderService, tmp_path) -> None:
        ws = str(tmp_path / "app")
        start = service.govern_request(
            "Build a todo webapp with localStorage",
            phase="start",
            context="MVP simple local no backend",
            workspace_path=ws,
        )
        mid = start["mission_id"]
        mission = service.db.get_mission(mid)
        for unknown in list(mission.unknowns):
            service.submit_user_answer(mid, unknown, f"Answer for {unknown}")

        refined = service.refine_plan(
            mid,
            [
                "Create index.html",
                "Add CSS layout",
                "Implement todo JS",
                "Persist in localStorage",
                "Manual test primary workflow",
            ],
        )
        assert refined["refined_objective"]
        steps = refined["ordered_plan_steps"]

        plan = service.govern_request(
            "todo",
            phase="plan",
            mission_id=mid,
            plan_steps=steps,
            workspace_path=ws,
        )
        assert plan["blocked"] is False

        act = service.govern_request(
            "todo",
            phase="act",
            mission_id=mid,
            action="Implement todo list UI in index.html",
            workspace_path=ws,
        )
        assert act["quality_gate"] in ("proceed", "caution")

        mission = service.db.get_mission(mid)
        for criterion in mission.success_criteria:
            result = service.mark_criterion_complete(mid, criterion)
            assert result["ok"] is True

        done = service.govern_request(
            "todo",
            phase="complete",
            mission_id=mid,
            workspace_path=ws,
        )
        assert done["blocked"] is False
        assert done["quality_gate"] == "stop"
        assert service.db.get_mission(mid).status == MissionStatus.COMPLETED

    def test_complete_blocked_without_criteria(self, service: GuiderService) -> None:
        mission = service.create_mission("Build a todo webapp", set_active=False)
        for unknown in list(mission.unknowns):
            service.record_decision(mission.id, unknown, "x", "y", DecisionSource.USER_ANSWER)
        result = service.govern_request(
            "todo", phase="complete", mission_id=mission.id
        )
        assert result["blocked"] is True
        assert result["quality_gate"] == "continue"


class TestObjectivesSimilar:
    def test_overlap(self) -> None:
        assert objectives_similar(
            "Build a personal website for our journey",
            "Build a personal website for our journey together",
        )
