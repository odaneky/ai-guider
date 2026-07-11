"""Mission session facade for phase gating and resume."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from guider.mission.models import Mission, MissionStatus
from guider.mission.plan_refine import refine_plan as refine_plan_heuristic

if TYPE_CHECKING:
    from guider.service import GuiderService


class MissionSession:
    """Thin session object: what's allowed next, resume context, plan refine."""

    PHASES = ("start", "plan", "act", "complete")

    def __init__(
        self,
        service: "GuiderService",
        mission_id: str,
        workspace: Optional[str] = None,
    ) -> None:
        self.service = service
        self.mission_id = mission_id
        self.workspace = workspace
        self._mission: Optional[Mission] = None

    @property
    def mission(self) -> Mission:
        if self._mission is None:
            self._mission = self.service._require_mission(self.mission_id)
        return self._mission

    def refresh(self) -> Mission:
        self._mission = self.service._require_mission(self.mission_id)
        return self._mission

    def can_proceed_to(self, phase: str) -> dict:
        phase = phase.lower().strip()
        mission = self.refresh()
        if phase not in self.PHASES:
            return {"allowed": False, "reason": f"Unknown phase: {phase}"}

        if phase == "start":
            return {"allowed": True, "reason": "Start/resume always allowed"}

        if phase == "plan":
            if self.service._has_pending_questions(self.mission_id):
                return {
                    "allowed": False,
                    "reason": "Unresolved pending questions — submit_user_answer first",
                }
            if mission.unknowns and mission.status == MissionStatus.PLANNING:
                return {
                    "allowed": False,
                    "reason": "Unresolved unknowns — submit_user_answer first",
                }
            return {"allowed": True, "reason": "Ready to plan"}

        if phase == "act":
            if mission.status == MissionStatus.COMPLETED:
                return {"allowed": False, "reason": "Mission already completed"}
            if mission.status == MissionStatus.BLOCKED:
                return {"allowed": False, "reason": "Mission blocked"}
            return {"allowed": True, "reason": "Act allowed (scope still validated)"}

        if phase == "complete":
            return {"allowed": True, "reason": "Completion check always allowed"}

        return {"allowed": False, "reason": "Not allowed"}

    def quality_gate(self, phase: str) -> str:
        check = self.can_proceed_to(phase)
        return "proceed" if check["allowed"] else "blocked"

    def resume_summary(self) -> dict:
        mission = self.refresh()
        pending = self.service.await_user_input(self.mission_id)
        events = self.service.db.list_events(self.mission_id, limit=5)
        progress = self.service.tracker.get_progress(mission)
        next_phase = "plan"
        if pending.get("blocked"):
            next_phase = "await_answers"
        elif mission.status == MissionStatus.COMPLETED:
            next_phase = "done"
        elif progress.get("criteria_progress_percent", 0) >= 100:
            next_phase = "complete"
        elif mission.status == MissionStatus.ACTIVE:
            next_phase = "act"

        return {
            "mission_id": mission.id,
            "workspace": self.workspace,
            "objective": mission.objective,
            "status": mission.status.value,
            "confidence_score": mission.confidence_score,
            "unknowns": mission.unknowns,
            "constraints": mission.constraints,
            "success_criteria": mission.success_criteria,
            "completed_items": mission.completed_items,
            "pending_questions": pending,
            "progress": progress,
            "recent_events": [e.model_dump(mode="json") for e in events],
            "suggested_next_phase": next_phase,
            "next_steps": pending.get("instruction")
            and [pending["instruction"]]
            or ["Call refine_plan then govern_request(phase='plan')"],
        }

    def refine_plan(self, draft_steps: Optional[List[str]] = None) -> dict:
        mission = self.refresh()
        decisions = self.service.db.list_decisions(self.mission_id)
        return refine_plan_heuristic(mission, decisions, draft_steps)

    def proceed(self, phase: str, **kwargs) -> dict:
        """Delegate to GuiderService.govern_request for the given phase."""
        check = self.can_proceed_to(phase)
        if not check["allowed"] and phase in ("plan",):
            return {
                "phase": phase,
                "quality_gate": "blocked",
                "blocked": True,
                "mission_id": self.mission_id,
                "reason": check["reason"],
                "next_steps": [check["reason"]],
            }
        request = kwargs.pop("request", self.mission.objective)
        return self.service.govern_request(
            request=request,
            phase=phase,
            mission_id=self.mission_id,
            workspace_path=self.workspace,
            **kwargs,
        )
