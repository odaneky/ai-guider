"""Extended governance methods for GuiderService."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from guider.config.loader import get_config
from guider.export import export_mission_yaml, generate_agents_md
from guider.mission.context_profiles import (
    detect_profile,
    filter_unknowns,
    get_profile_questions,
)
from guider.mission.models import (
    Decision,
    DecisionSource,
    Mission,
    MissionEvent,
    MissionEventType,
    MissionStatus,
    PendingQuestion,
)
from guider.mission.templates import get_template, list_templates
from guider.preferences import PreferenceStore
from guider.reporting import governance_report
from guider.validators.file_scope import FileScopeValidator


class GovernanceMixin:
    """Mixin adding v0.2 governance capabilities to GuiderService."""

    def _init_governance_extras(self) -> None:
        self.file_scope_validator = FileScopeValidator()
        self.preferences = PreferenceStore(self.db)

    def _log_tool(self, name: str, mission_id: Optional[str] = None) -> None:
        self.db.log_tool_call(name, mission_id)

    def list_mission_templates(self) -> list:
        self._log_tool("list_mission_templates")
        return list_templates()

    def create_mission_from_template(
        self,
        template_id: str,
        request: str,
        context: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        self._log_tool("create_mission_from_template")
        template = get_template(template_id)
        if not template:
            raise ValueError(f"Unknown template: {template_id}")

        pref_context = self.preferences.apply_to_mission_context()
        full_context = "\n".join(filter(None, [context, pref_context]))

        mission = self.builder.build(request, full_context)
        mission.template_id = template_id
        mission.success_criteria = list(template.get("success_criteria", mission.success_criteria))
        mission.constraints = list(dict.fromkeys(
            mission.constraints + template.get("constraints", [])
        ))
        mission.scope_max_files = template.get("scope_max_files", 20)

        profile = template.get("context_profile", detect_profile(request, full_context))
        skip = [s.lower() for s in template.get("default_unknowns_skip", [])]
        mission.unknowns = filter_unknowns(
            [u for u in mission.unknowns if u.lower() not in skip],
            profile,
        )

        self.db.save_mission(mission)
        self.db.record_event(MissionEvent(
            mission_id=mission.id,
            event_type=MissionEventType.CREATED,
            message=f"Mission from template '{template_id}'",
            metadata={"template": template_id, "profile": profile},
        ))
        from guider.workspace import set_active_mission
        set_active_mission(self.db, mission.id, workspace_path)

        pending = self.await_user_input(mission.id)
        return {
            "mission": mission.model_dump(mode="json"),
            "template": template_id,
            "profile": profile,
            "pending_questions": pending,
        }

    def await_user_input(self, mission_id: str) -> dict:
        """Create pending questions from unresolved unknowns. Blocks plan until answered."""
        self._log_tool("await_user_input", mission_id)
        mission = self._require_mission(mission_id)
        profile = detect_profile(mission.objective, mission.context or "", "")

        existing = {q.unknown for q in self.db.get_unanswered_questions(mission_id)}
        created = []

        for unknown in mission.unknowns:
            if unknown in existing:
                continue
            pref = self.preferences.suggest_for_unknown(unknown)
            questions = get_profile_questions(unknown, profile)
            q_text = questions[0]
            if pref:
                q_text = f"{q_text} (suggested from preferences: {pref})"

            pq = PendingQuestion(
                mission_id=mission_id,
                unknown=unknown,
                question=q_text,
                severity="high" if "compliance" in unknown.lower() else "medium",
            )
            self.db.save_pending_question(pq)
            created.append(pq.model_dump(mode="json"))

            self.db.record_event(MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.QUESTION_ASKED,
                message=f"Question for: {unknown}",
                metadata={"question": q_text},
            ))

        unanswered = self.db.get_unanswered_questions(mission_id)
        questions_out = []
        for q in unanswered:
            data = q.model_dump(mode="json")
            pref = self.preferences.suggest_for_unknown(q.unknown)
            data["suggested_answer"] = pref
            questions_out.append(data)

        return {
            "mission_id": mission_id,
            "pending_count": len(unanswered),
            "blocked": len(unanswered) > 0,
            "questions": questions_out,
            "new_questions": created,
            "instruction": (
                "Ask the user these questions, then call submit_user_answer for each response."
                if unanswered
                else "All questions answered — call refine_plan, then govern_request(phase='plan')"
            ),
        }

    def submit_user_answer(
        self, mission_id: str, unknown: str, answer: str
    ) -> dict:
        """Record a user-confirmed answer. Resolves unknown with full confidence."""
        self._log_tool("submit_user_answer", mission_id)
        mission = self._require_mission(mission_id)

        for pq in self.db.list_pending_questions(mission_id):
            if pq.unknown.lower() == unknown.lower() or unknown.lower() in pq.unknown.lower():
                pq.answered = True
                pq.answer = answer
                self.db.save_pending_question(pq)

        result = self.record_decision(
            mission_id,
            title=unknown,
            description=answer,
            reason="User-confirmed answer",
            source=DecisionSource.USER_ANSWER,
        )

        self.db.record_event(MissionEvent(
            mission_id=mission_id,
            event_type=MissionEventType.USER_ANSWERED,
            message=f"User answered: {unknown}",
            metadata={"answer": answer},
        ))

        pref_key = unknown.lower().replace(" ", "_")[:40]
        self.preferences.save(pref_key, answer, "From user answer")

        return {
            **result,
            "user_confirmed": True,
            "remaining_questions": len(self.db.get_unanswered_questions(mission_id)),
        }

    def pivot_decision(
        self,
        mission_id: str,
        description: str,
        reason: str,
        new_constraints: Optional[List[str]] = None,
    ) -> dict:
        """Record a scope/technology pivot and re-validate mission state."""
        self._log_tool("pivot_decision", mission_id)
        mission = self._require_mission(mission_id)

        if new_constraints:
            for c in new_constraints:
                if c not in mission.constraints:
                    mission.constraints.append(c)

        mission.status = MissionStatus.PLANNING
        self.db.save_mission(mission)

        decision = self.record_decision(
            mission_id,
            title="Pivot",
            description=description,
            reason=reason,
            source=DecisionSource.USER_ANSWER,
        )

        self.db.record_event(MissionEvent(
            mission_id=mission_id,
            event_type=MissionEventType.PIVOT_RECORDED,
            message=f"Pivot: {description[:80]}",
            metadata={"reason": reason},
        ))

        return {
            "pivot_recorded": True,
            "decision": decision,
            "mission_status": mission.status.value,
            "next_steps": [
                "Call govern_request(phase='plan') with revised plan steps",
                "Re-validate scope for new direction",
            ],
        }

    def validate_scope_with_files(
        self,
        mission_id: str,
        action: str,
        files: Optional[List[str]] = None,
    ) -> dict:
        """Validate action scope and optional file paths."""
        scope = self.validate_scope(mission_id, action)
        if not files:
            return scope

        mission = self._require_mission(mission_id)
        file_result = self.file_scope_validator.validate(mission, files)
        self.db.save_validator_result(file_result, mission_id)

        combined_verdict = scope["verdict"]
        if not file_result.passed:
            combined_verdict = "reject"

        return {
            **scope,
            "verdict": combined_verdict,
            "approved": combined_verdict == "approve",
            "blocked": combined_verdict == "reject",
            "file_validation": file_result.model_dump(),
        }

    def _has_pending_questions(self, mission_id: str) -> bool:
        config = self.policy_engine.config or get_config()
        if not config.rules.require_user_confirmation:
            return False
        if config.profile == "permissive":
            return False
        return len(self.db.get_unanswered_questions(mission_id)) > 0

    def _run_plugins_for_act(self, mission: Mission, action: str) -> List[dict]:
        results = []
        for name in self.plugins.list_plugins():
            plugin = self.plugins.get_plugin(name)
            if not plugin:
                continue
            if name == "software_engineering":
                for method_name in ("review_code_change", "detect_architecture_issue"):
                    method = getattr(plugin, method_name, None)
                    if method:
                        r = method(mission, action)
                        results.append(r.model_dump())
            elif name == "personal":
                for method_name in ("validate_design_scope", "check_content_readiness"):
                    method = getattr(plugin, method_name, None)
                    if method:
                        r = method(mission, action)
                        results.append(r.model_dump())
            else:
                for vname, vfn in plugin.register_validators().items():
                    if "test" in vname:
                        continue
                    try:
                        r = vfn(mission, action)
                        results.append(r.model_dump())
                    except TypeError:
                        continue
        return results

    def _plugin_gate(self, plugin_results: List[dict]) -> str:
        """Map plugin scores to proceed | caution | reject."""
        if not plugin_results:
            return "proceed"
        worst = "proceed"
        for r in plugin_results:
            score = r.get("score", 100)
            if score < 40:
                return "reject"
            if score < 60 or not r.get("passed", True):
                worst = "caution"
        return worst

    def refine_plan(
        self, mission_id: str, draft_steps: Optional[List[str]] = None
    ) -> dict:
        """Sharpen plan after objective is locked."""
        self._log_tool("refine_plan", mission_id)
        from guider.mission.session import MissionSession

        session = MissionSession(self, mission_id)
        return session.refine_plan(draft_steps)

    def resume_mission(
        self, workspace_path: Optional[str] = None, mission_id: Optional[str] = None
    ) -> dict:
        """Return resume summary for active or specified mission."""
        self._log_tool("resume_mission", mission_id)
        from guider.mission.session import MissionSession
        from guider.workspace import get_active_mission_id, get_workspace_key

        mid = mission_id or get_active_mission_id(self.db, workspace_path)
        if not mid:
            return {
                "mission_id": None,
                "workspace": get_workspace_key(workspace_path),
                "next_steps": ["Call govern_request(phase='start') to begin"],
            }
        session = MissionSession(self, mid, get_workspace_key(workspace_path))
        return session.resume_summary()

    def export_mission(self, mission_id: str, project_path: str) -> dict:
        self._log_tool("export_mission", mission_id)
        mission = self._require_mission(mission_id)
        path = Path(project_path)
        yaml_path = export_mission_yaml(mission, self.db, path)
        agents_path = generate_agents_md(mission, self.db, path)
        return {
            "mission_yaml": str(yaml_path),
            "agents_md": str(agents_path),
        }

    def get_governance_report(self, mission_id: Optional[str] = None) -> dict:
        self._log_tool("get_governance_report", mission_id)
        return governance_report(self.db, mission_id)

    def save_preference(self, key: str, value: str, reason: str = "") -> dict:
        self._log_tool("save_preference")
        self.preferences.save(key, value, reason)
        return {"key": key, "value": value, "saved": True}

    def list_preferences(self) -> dict:
        self._log_tool("list_preferences")
        return {"preferences": self.preferences.list_all()}
