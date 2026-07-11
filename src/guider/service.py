from __future__ import annotations

from typing import List, Optional

from guider.config.loader import get_config
from guider.governance import GovernanceMixin
from guider.mission.builder import MissionBuilder
from guider.mission.classifier import (
    classify_task,
    match_unknowns_for_decision,
    objectives_similar,
)
from guider.mission.context_profiles import detect_profile, filter_unknowns, get_profile_questions
from guider.mission.lifecycle import MissionLifecycle
from guider.mission.models import Decision, DecisionSource, Mission, MissionEvent, MissionEventType, MissionStatus
from guider.mission.session import MissionSession
from guider.mission.tracker import MissionTracker
from guider.plugins.loader import load_plugins
from guider.policies.engine import PolicyEngine
from guider.storage.database import Database, get_database
from guider.validators.assumptions import AssumptionsValidator
from guider.validators.completion import CompletionValidator
from guider.validators.consistency import ConsistencyValidator
from guider.validators.risk import RiskValidator
from guider.validators.scope import ScopeValidator
from guider.workspace import (
    clear_active_mission,
    get_active_mission_id,
    get_workspace_key,
    set_active_mission,
)

class GuiderService(GovernanceMixin):
    """Core service layer orchestrating missions, validators, and storage."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_database()
        self.builder = MissionBuilder()
        self.tracker = MissionTracker()
        self.lifecycle = MissionLifecycle()
        self.policy_engine = PolicyEngine()
        self.scope_validator = ScopeValidator(self.policy_engine)
        self.assumptions_validator = AssumptionsValidator()
        self.completion_validator = CompletionValidator()
        self.consistency_validator = ConsistencyValidator()
        self.risk_validator = RiskValidator()
        self.plugins = load_plugins()
        self._init_governance_extras()
        self._codebase_map_cache: dict = {}

    def classify_task(self, request: str) -> dict:
        result = classify_task(request)
        config = get_config()
        if config.profile == "light" and result["category"] == "trivial":
            result["requires_mission"] = False
        elif result["category"] in config.rules.require_mission_for:
            result["requires_mission"] = True
        return result

    def create_mission(
        self,
        request: str,
        context: Optional[str] = None,
        workspace_path: Optional[str] = None,
        set_active: bool = True,
    ) -> Mission:
        mission = self.builder.build(request, context)
        self.db.save_mission(mission)
        self.db.record_event(
            MissionEvent(
                mission_id=mission.id,
                event_type=MissionEventType.CREATED,
                message=f"Mission created: {mission.objective[:80]}",
            )
        )
        if set_active:
            set_active_mission(self.db, mission.id, workspace_path)
        for plugin in [self.plugins.get_plugin(n) for n in self.plugins.list_plugins()]:
            if plugin:
                plugin.on_mission_created(mission)
        return mission

    def set_active_mission(self, mission_id: str, workspace_path: Optional[str] = None) -> dict:
        self._require_mission(mission_id)
        workspace_key = set_active_mission(self.db, mission_id, workspace_path)
        return {"mission_id": mission_id, "workspace": workspace_key}

    def get_active_mission(self, workspace_path: Optional[str] = None) -> dict:
        mission_id = get_active_mission_id(self.db, workspace_path)
        if not mission_id:
            return {"mission_id": None, "workspace": get_workspace_key(workspace_path)}
        mission = self.db.get_mission(mission_id)
        if not mission:
            clear_active_mission(self.db, workspace_path)
            return {"mission_id": None, "workspace": get_workspace_key(workspace_path)}
        return {
            "mission_id": mission_id,
            "workspace": get_workspace_key(workspace_path),
            "objective": mission.objective,
            "status": mission.status.value,
            "confidence_score": mission.confidence_score,
        }

    def _resolve_mission_id(
        self, mission_id: Optional[str], workspace_path: Optional[str] = None
    ) -> str:
        if mission_id:
            return mission_id
        active = get_active_mission_id(self.db, workspace_path)
        if not active:
            raise ValueError("No mission_id provided and no active mission for workspace")
        return active

    def govern_request(
        self,
        request: str,
        phase: str = "start",
        context: Optional[str] = None,
        mission_id: Optional[str] = None,
        action: Optional[str] = None,
        plan_steps: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        """Orchestrate governance workflow by phase."""
        phase = phase.lower().strip()
        classification = self.classify_task(request)

        if phase == "start":
            if not classification["requires_mission"]:
                return {
                    "phase": "start",
                    "quality_gate": "proceed",
                    "blocked": False,
                    "requires_mission": False,
                    "classification": classification,
                    "next_steps": ["Proceed without full mission workflow (trivial task)"],
                }

            reused = False
            active_id = get_active_mission_id(self.db, workspace_path)
            mission: Optional[Mission] = None
            if active_id:
                existing = self.db.get_mission(active_id)
                if (
                    existing
                    and existing.status
                    not in (MissionStatus.COMPLETED, MissionStatus.CANCELLED)
                    and objectives_similar(existing.objective, request)
                ):
                    mission = existing
                    reused = True

            if mission is None:
                mission = self.create_mission(request, context, workspace_path)
            else:
                set_active_mission(self.db, mission.id, workspace_path)

            unknowns = self.analyze_unknowns(request, context, mission.id)
            pending = self.await_user_input(mission.id)
            policy = self.policy_engine.evaluate_mission(mission)
            next_steps = []
            if reused:
                next_steps.append(
                    f"Resumed existing mission {mission.id} — do not create a duplicate"
                )
            if pending["blocked"]:
                if mission.status != MissionStatus.BLOCKED:
                    self.lifecycle.block(mission)
                    self.db.save_mission(mission)
                next_steps.append("Ask user the pending questions, then submit_user_answer for each")
                for q in pending.get("questions", [])[:5]:
                    next_steps.append(f"Ask user: {q.get('question', '')}")
            elif policy.require_clarification:
                next_steps.append("Call submit_user_answer for each unknown")
                for item in unknowns.get("unknowns", []):
                    for q in item.get("recommended_questions", [])[:1]:
                        next_steps.append(f"Ask user: {q}")
            else:
                next_steps.append("Call refine_plan, then govern_request(phase='plan') with plan steps")

            blocked = pending["blocked"] or policy.require_clarification
            payload = {
                "phase": "start",
                "quality_gate": "blocked" if blocked else "proceed",
                "blocked": blocked,
                "requires_mission": True,
                "classification": classification,
                "mission_id": mission.id,
                "mission": mission.model_dump(mode="json"),
                "resumed": reused,
                "unknowns": unknowns,
                "pending_questions": pending,
                "policy": {
                    "action": policy.action,
                    "reason": policy.reason,
                    "require_clarification": policy.require_clarification,
                },
                "next_steps": next_steps,
            }
            if reused:
                payload["resume"] = MissionSession(
                    self, mission.id, get_workspace_key(workspace_path)
                ).resume_summary()
            return payload

        resolved_id = self._resolve_mission_id(mission_id, workspace_path)

        if phase == "plan":
            session = MissionSession(self, resolved_id, get_workspace_key(workspace_path))
            gate_check = session.can_proceed_to("plan")
            if not gate_check["allowed"]:
                pending = self.await_user_input(resolved_id)
                return {
                    "phase": "plan",
                    "quality_gate": "blocked",
                    "blocked": True,
                    "mission_id": resolved_id,
                    "reason": gate_check["reason"],
                    "pending_questions": pending,
                    "next_steps": ["Call submit_user_answer for each question before planning"],
                }
            if not plan_steps:
                refined = self.refine_plan(resolved_id)
                return {
                    "phase": "plan",
                    "quality_gate": "needs_plan",
                    "blocked": True,
                    "mission_id": resolved_id,
                    "refined_plan": refined,
                    "next_steps": [
                        "Review refined_plan.ordered_plan_steps",
                        "Call govern_request(phase='plan', plan_steps=...) to approve",
                        f"Mission objective: {session.mission.objective}",
                    ],
                }
            review = self.review_plan(resolved_id, plan_steps)
            gate = "proceed" if review["approved"] else "blocked"
            result = {
                "phase": "plan",
                "quality_gate": gate,
                "blocked": not review["approved"],
                "mission_id": resolved_id,
                "plan_review": review,
                "next_steps": (
                    ["Call govern_request(phase='act') before each major implementation step"]
                    if review["approved"]
                    else ["Revise plan to address issues, then call govern_request(phase='plan') again"]
                ),
            }
            if review["approved"] and workspace_path:
                try:
                    result["export"] = self.export_mission(resolved_id, workspace_path)
                except Exception:
                    pass
            return result

        if phase == "act":
            if not action:
                raise ValueError("govern_request(phase='act') requires action")
            mission = self._require_mission(resolved_id)
            if self._validator_enabled("scope"):
                if files:
                    scope = self.validate_scope_with_files(resolved_id, action, files)
                else:
                    scope = self.validate_scope(resolved_id, action)
            else:
                scope = {
                    "approved": True,
                    "verdict": "approve",
                    "must_confirm_with_user": False,
                    "reason": "Scope validator disabled",
                }
            plugin_results = self._run_plugins_for_act(mission, action)
            plugin_gate = self._plugin_gate(plugin_results)
            if scope["verdict"] == "reject" or plugin_gate == "reject":
                gate = "reject"
            elif scope["verdict"] == "caution" or plugin_gate == "caution":
                gate = "caution"
            else:
                gate = "proceed"
            if gate == "reject":
                config = self.policy_engine.config or get_config()
                if config.profile == "strict" and mission.status != MissionStatus.BLOCKED:
                    self.lifecycle.block(mission)
                    self.db.save_mission(mission)
                from guider.hooks_runtime import clear_act_grant

                clear_act_grant(self.db, workspace_path)
                act_grant = None
            else:
                from guider.hooks_runtime import record_act_grant

                act_grant = record_act_grant(
                    self.db,
                    workspace_path,
                    mission_id=resolved_id,
                    action=action,
                    files=files,
                    verdict=gate if gate != "proceed" else scope.get("verdict", "approve"),
                )
            return {
                "phase": "act",
                "quality_gate": gate,
                "blocked": gate == "reject",
                "mission_id": resolved_id,
                "scope": scope,
                "plugin_results": plugin_results,
                "plugin_gate": plugin_gate,
                "act_grant": act_grant,
                "next_steps": (
                    ["Confirm with user before proceeding"]
                    if gate == "caution" or scope.get("must_confirm_with_user")
                    else ["Proceed with implementation — Cursor hooks will allow granted files"]
                    if gate == "proceed"
                    else ["Do not implement this action"]
                ),
            }

        if phase == "complete":
            completion = self.validate_completion(resolved_id)
            mission = self._require_mission(resolved_id)
            if completion["complete"]:
                self.lifecycle.complete(mission)
                self.db.save_mission(mission)
            gate = "stop" if completion.get("recommend_stopping") else "continue"
            incomplete = not completion.get("complete", False)
            return {
                "phase": "complete",
                "quality_gate": gate,
                "blocked": incomplete,
                "mission_id": resolved_id,
                "completion": completion,
                "next_steps": (
                    ["Mission complete — stop further scope expansion"]
                    if completion.get("recommend_stopping")
                    else [
                        "Call mark_criterion_complete for each success criterion",
                        "Address missing_items before claiming completion",
                    ]
                ),
            }

        raise ValueError(f"Unknown govern_request phase: {phase}")

    def analyze_unknowns(
        self, request: str, context: Optional[str] = None, mission_id: Optional[str] = None
    ) -> dict:
        mission = None
        if mission_id:
            mission = self.db.get_mission(mission_id)

        unknowns = mission.unknowns if mission else self.builder._detect_unknowns(request, context)
        profile = detect_profile(
            request,
            context or "",
            mission.template_id or "" if mission else "",
        )
        if mission and mission.template_id:
            from guider.mission.templates import get_template
            tmpl = get_template(mission.template_id)
            if tmpl:
                profile = tmpl.get("context_profile", profile)

        unknowns = filter_unknowns(unknowns, profile)
        analyzed = []

        for unknown in unknowns:
            key = unknown.lower()
            severity = "high" if key in ("compliance requirements", "authentication") else "medium"
            if "detailed" in key:
                severity = "high"

            questions = get_profile_questions(unknown, profile)
            pref = self.preferences.suggest_for_unknown(unknown)
            if pref:
                questions = [f"{questions[0]} (preference: {pref})"] + questions[1:]

            analyzed.append({
                "unknown": unknown,
                "severity": severity,
                "recommended_questions": questions,
            })

            if mission:
                self.db.record_event(
                    MissionEvent(
                        mission_id=mission.id,
                        event_type=MissionEventType.UNKNOWN_DETECTED,
                        message=f"Unknown detected: {unknown}",
                        metadata={"severity": severity},
                    )
                )

        return {
            "unknowns": analyzed,
            "count": len(analyzed),
            "mission_id": mission.id if mission else None,
        }

    def _validator_enabled(self, name: str) -> bool:
        config = self.policy_engine.config or get_config()
        validators = getattr(config, "validators", None)
        if validators is None:
            return True
        entry = getattr(validators, name, None)
        if entry is None:
            return True
        return bool(getattr(entry, "enabled", True))

    def validate_scope(self, mission_id: str, action: str) -> dict:
        if not self._validator_enabled("scope"):
            return {
                "approved": True,
                "verdict": "approve",
                "must_confirm_with_user": False,
                "confidence": 1.0,
                "reason": "Scope validator disabled in config",
                "validator": {"name": "scope_validator", "score": 100, "passed": True, "reason": "disabled"},
                "policy": {"action": "approve", "rules_triggered": []},
            }
        mission = self._require_mission(mission_id)
        decisions = self.db.list_decisions(mission_id)
        result = self.scope_validator.validate(mission, action, decisions)
        policy = self.policy_engine.evaluate_scope(result)
        self.db.save_validator_result(result, mission_id)

        verdict = result.details.get("verdict", "reject")
        approved = verdict == "approve" and not policy.reject_action

        because = []
        if result.details.get("keyword_overlap") is not None:
            because.append(f"Keyword overlap with objective")
        if result.details.get("decision_conflicts"):
            because.append(f"Conflicts with decisions: {result.details['decision_conflicts']}")
        fix = (
            "Confirm with user or narrow action to match objective/decisions"
            if verdict != "approve"
            else "Proceed"
        )

        self.db.record_event(
            MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.SCOPE_VALIDATED,
                message=f"Scope validation: {verdict}",
                metadata={"action": action, "score": result.score, "verdict": verdict},
            )
        )

        return {
            "approved": approved,
            "verdict": verdict,
            "must_confirm_with_user": policy.must_confirm_with_user,
            "confidence": result.score / 100,
            "reason": policy.reason,
            "because": because or [result.reason],
            "fix": fix,
            "validator": result.model_dump(),
            "policy": {
                "action": policy.action,
                "rules_triggered": policy.rules_triggered,
            },
        }

    def mark_criterion_complete(self, mission_id: str, criterion: str) -> dict:
        """Mark a success criterion as complete."""
        self._log_tool("mark_criterion_complete", mission_id)
        mission = self._require_mission(mission_id)
        if criterion not in mission.success_criteria:
            return {
                "ok": False,
                "reason": f"Unknown criterion: {criterion}",
                "success_criteria": mission.success_criteria,
                "completed_items": mission.completed_items,
            }
        self.tracker.mark_criterion_complete(mission, criterion)
        self.db.save_mission(mission)
        self.db.record_event(
            MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.TASK_COMPLETED,
                message=f"Criterion complete: {criterion[:80]}",
                metadata={"criterion": criterion},
            )
        )
        progress = self.tracker.get_progress(mission)
        return {
            "ok": True,
            "criterion": criterion,
            "completed_items": mission.completed_items,
            "progress": progress,
        }

    def mark_criteria_complete(self, mission_id: str, criteria: List[str]) -> dict:
        """Mark multiple success criteria as complete."""
        results = [self.mark_criterion_complete(mission_id, c) for c in criteria]
        mission = self._require_mission(mission_id)
        return {
            "ok": all(r.get("ok") for r in results),
            "results": results,
            "completed_items": mission.completed_items,
            "progress": self.tracker.get_progress(mission),
        }

    def detect_assumptions(self, statement: str, mission_id: Optional[str] = None) -> dict:
        result = self.assumptions_validator.validate(statement)
        self.db.save_validator_result(result, mission_id)

        assumptions = result.details.get("assumptions", [])
        if mission_id and assumptions:
            mission = self.db.get_mission(mission_id)
            if mission:
                for item in assumptions:
                    text = item.get("text") or item.get("assumption") or str(item)
                    self.tracker.add_assumption(mission, text)
                self.db.save_mission(mission)

        return {
            "assumptions": assumptions,
            "count": len(assumptions),
            "severity": (
                "high"
                if any(a.get("severity") == "high" for a in assumptions)
                else "medium" if assumptions else "none"
            ),
            "validator": result.model_dump(),
        }

    def review_plan(self, mission_id: str, plan_steps: List[str]) -> dict:
        mission = self._require_mission(mission_id)
        issues = []
        risk_result = None
        consistency_result = None

        if self._validator_enabled("risk"):
            risk_result = self.risk_validator.validate_plan(mission, plan_steps)
            if risk_result.details.get("risks"):
                issues.extend(risk_result.details["risks"])
            self.db.save_validator_result(risk_result, mission_id)
        if self._validator_enabled("consistency"):
            consistency_result = self.consistency_validator.validate(mission)
            if not consistency_result.passed:
                issues.extend(consistency_result.details.get("issues", []))

        # Plugin plan checks
        plugin_results = []
        se = self.plugins.get_plugin("software_engineering")
        if se:
            tr = se.check_tests(mission, " ".join(plan_steps))
            plugin_results.append(tr.model_dump())
            # Only hard-fail plan on severe plugin scores; missing tests is caution
            if tr.score < 40:
                issues.append(tr.reason)

        overengineering = any(
            "over-engineer" in i.lower() or "too many steps" in i.lower() for i in issues
        )
        missing_steps = any("missing" in i.lower() for i in issues)

        scores = []
        if risk_result:
            scores.append(risk_result.score)
        if consistency_result:
            scores.append(consistency_result.score)
        # Soft-include plugin scores only when severe
        for pr in plugin_results:
            if pr.get("score", 100) < 40:
                scores.append(pr["score"])
        score = min(scores) if scores else 100
        approved = score >= 60 and not overengineering

        if approved and mission.status in (MissionStatus.PLANNING, MissionStatus.BLOCKED):
            self.lifecycle.activate(mission)
            self.db.save_mission(mission)

        self.db.record_event(
            MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.PLAN_APPROVED if approved else MissionEventType.PLAN_REJECTED,
                message=f"Plan review: {'approved' if approved else 'needs revision'}",
                metadata={"step_count": len(plan_steps), "score": score},
            )
        )

        return {
            "approved": approved,
            "score": score,
            "issues": issues,
            "overengineering": overengineering,
            "missing_steps": missing_steps,
            "dependencies_noted": not any("dependency" in i.lower() for i in issues),
            "risk_validator": risk_result.model_dump() if risk_result else None,
            "consistency_validator": consistency_result.model_dump() if consistency_result else None,
            "plugin_results": plugin_results,
        }

    def validate_completion(self, mission_id: str) -> dict:
        mission = self._require_mission(mission_id)
        if not self._validator_enabled("completion"):
            return {
                "complete": True,
                "missing_items": [],
                "score": 100,
                "recommend_stopping": True,
                "validator": {"name": "completion_validator", "score": 100, "passed": True, "reason": "disabled"},
            }
        result = self.completion_validator.validate(mission)
        policy = self.policy_engine.evaluate_completion(result)
        self.db.save_validator_result(result, mission_id)

        complete = result.details.get("complete", False)
        self.db.record_event(
            MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.COMPLETION_CHECKED,
                message=f"Completion check: {'complete' if complete else 'incomplete'}",
                metadata={"score": result.score},
            )
        )

        return {
            "complete": complete,
            "missing_items": result.details.get("missing_items", []),
            "score": result.score,
            "recommend_stopping": policy.recommend_stopping,
            "validator": result.model_dump(),
        }

    def record_decision(
        self,
        mission_id: str,
        title: str,
        description: str,
        reason: str,
        source: DecisionSource = DecisionSource.AGENT_ASSUMPTION,
    ) -> dict:
        self._log_tool("record_decision", mission_id)
        config = self.policy_engine.config or get_config()
        mission = self._require_mission(mission_id)

        if (
            config.rules.require_user_confirmation
            and config.profile == "strict"
            and source == DecisionSource.AGENT_ASSUMPTION
            and mission.unknowns
        ):
            return {
                "rejected": True,
                "reason": "Strict mode: use submit_user_answer instead of agent assumptions",
                "remaining_unknowns": mission.unknowns,
                "instruction": "Ask the user, then call submit_user_answer",
            }

        decision = Decision(
            mission_id=mission_id,
            title=title,
            description=description,
            reason=reason,
            source=source,
        )
        self.db.save_decision(decision)

        resolved = self._apply_decision_to_mission(mission, title, source)
        self.db.save_mission(mission)

        self.db.record_event(
            MissionEvent(
                mission_id=mission_id,
                event_type=MissionEventType.DECISION_RECORDED,
                message=f"Decision: {title}",
                metadata={"reason": reason, "resolved_unknowns": resolved},
            )
        )
        for plugin in [self.plugins.get_plugin(n) for n in self.plugins.list_plugins()]:
            if plugin:
                plugin.on_decision_recorded(mission, title)

        policy = self.policy_engine.evaluate_mission(mission)
        return {
            **decision.model_dump(mode="json"),
            "source": source.value,
            "resolved_unknowns": resolved,
            "mission_status": mission.status.value,
            "confidence_score": mission.confidence_score,
            "remaining_unknowns": mission.unknowns,
            "policy": {
                "action": policy.action,
                "reason": policy.reason,
                "require_clarification": policy.require_clarification,
            },
        }

    def _apply_decision_to_mission(
        self, mission: Mission, title: str, source: DecisionSource = DecisionSource.AGENT_ASSUMPTION
    ) -> List[str]:
        resolved: List[str] = []
        targets = match_unknowns_for_decision(title)

        for target in targets:
            for unknown in list(mission.unknowns):
                if unknown.lower() == target or target in unknown.lower():
                    self.tracker.resolve_unknown(mission, unknown)
                    resolved.append(unknown)

        if not targets:
            for unknown in list(mission.unknowns):
                if unknown.lower() in title.lower() or title.lower() in unknown.lower():
                    self.tracker.resolve_unknown(mission, unknown)
                    resolved.append(unknown)

        if resolved:
            boost = 0.08 if source == DecisionSource.USER_ANSWER else 0.05
            mission.confidence_score = min(1.0, round(mission.confidence_score + boost * len(resolved), 2))

        if not mission.unknowns and mission.status in (
            MissionStatus.PLANNING,
            MissionStatus.BLOCKED,
        ):
            self.lifecycle.activate(mission)

        return resolved

    def map_codebase(
        self,
        workspace_path: Optional[str] = None,
        max_depth: int = 4,
        refresh: bool = False,
    ) -> dict:
        """Build a local codebase map for agent orientation (no project file writes)."""
        from pathlib import Path

        from guider.codebase_map import build_codebase_map, workspace_fingerprint

        root = Path(get_workspace_key(workspace_path))
        cache_key = str(root)
        cached = self._codebase_map_cache.get(cache_key)

        if not refresh and cached and cached.get("max_depth") == max_depth:
            try:
                fp = workspace_fingerprint(root, max_depth=max_depth)
            except OSError:
                fp = ""
            if fp and cached.get("fingerprint") == fp:
                self._log_tool("map_codebase")
                return {**cached["map"], "cached": True}

        self._log_tool("map_codebase")
        result = build_codebase_map(root, max_depth=max_depth)
        self._codebase_map_cache[cache_key] = {
            "fingerprint": result.get("fingerprint"),
            "max_depth": max_depth,
            "map": result,
        }
        return {**result, "cached": False}

    def get_mission_state(self, mission_id: str) -> dict:
        mission = self._require_mission(mission_id)
        state = self.tracker.get_state_summary(mission)
        events = self.db.list_events(mission_id, limit=10)
        decisions = self.db.list_decisions(mission_id)
        policy = self.policy_engine.evaluate_mission(mission)

        return {
            **state,
            "recent_events": [e.model_dump(mode="json") for e in events],
            "decisions": [d.model_dump(mode="json") for d in decisions],
            "policy": {
                "action": policy.action,
                "reason": policy.reason,
                "require_clarification": policy.require_clarification,
            },
            "plugins": self.plugins.list_plugins(),
        }

    def _require_mission(self, mission_id: str) -> Mission:
        mission = self.db.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        return mission
