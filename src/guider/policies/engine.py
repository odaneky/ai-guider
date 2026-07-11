from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from guider.config.loader import GuiderConfig
from guider.mission.models import Mission, MissionStatus, ValidatorResult
from guider.policies.profiles import get_profile


@dataclass
class PolicyDecision:
    action: str
    reason: str
    require_clarification: bool = False
    reject_action: bool = False
    recommend_stopping: bool = False
    must_confirm_with_user: bool = False
    rules_triggered: List[str] = field(default_factory=list)


class PolicyEngine:
    """Evaluate governance rules against mission and validator state."""

    def __init__(self, config: Optional[GuiderConfig] = None) -> None:
        self.config = config
        self._profile_overrides: Optional[dict] = None

    def _get_thresholds(self) -> dict:
        if self.config is None:
            from guider.config.loader import get_config

            self.config = get_config()

        profile = get_profile(self.config.profile)
        return {
            "min_confidence_threshold": profile.get(
                "min_confidence_threshold",
                self.config.rules.min_confidence_threshold,
            ),
            "min_scope_score": profile.get(
                "min_scope_score", self.config.rules.min_scope_score
            ),
            "caution_scope_max": profile.get(
                "caution_scope_max", self.config.rules.caution_scope_max
            ),
            "completion_stop_score": profile.get(
                "completion_stop_score", self.config.rules.completion_stop_score
            ),
        }

    def evaluate_mission(self, mission: Mission) -> PolicyDecision:
        thresholds = self._get_thresholds()
        rules: List[str] = []

        if mission.status == MissionStatus.COMPLETED:
            return PolicyDecision(
                action="stop",
                reason="Mission already completed",
                recommend_stopping=True,
                rules_triggered=["mission_completed"],
            )

        if mission.status == MissionStatus.ACTIVE and not mission.unknowns:
            if mission.confidence_score >= thresholds["min_confidence_threshold"]:
                return PolicyDecision(
                    action="proceed",
                    reason="Active mission with resolved unknowns",
                    rules_triggered=rules,
                )

        if mission.unknowns and mission.status == MissionStatus.PLANNING:
            rules.append("unresolved_unknowns_in_planning")
            return PolicyDecision(
                action="require_clarification",
                reason=f"Resolve {len(mission.unknowns)} unknown(s) via submit_user_answer before execution",
                require_clarification=True,
                rules_triggered=rules,
            )

        if mission.confidence_score < thresholds["min_confidence_threshold"]:
            rules.append(
                f"mission_confidence ({mission.confidence_score}) < "
                f"{thresholds['min_confidence_threshold']}"
            )
            return PolicyDecision(
                action="require_clarification",
                reason="Mission confidence is below threshold — clarify unknowns before proceeding",
                require_clarification=True,
                rules_triggered=rules,
            )

        return PolicyDecision(
            action="proceed",
            reason="Mission meets policy thresholds",
            rules_triggered=rules,
        )

    def evaluate_scope(self, result: ValidatorResult) -> PolicyDecision:
        thresholds = self._get_thresholds()
        rules: List[str] = []
        score = result.score
        verdict = result.details.get("verdict", "reject")

        if verdict == "reject" or score < thresholds["min_scope_score"]:
            rules.append(
                f"scope_score ({score}) < {thresholds['min_scope_score']}"
            )
            return PolicyDecision(
                action="reject",
                reason=result.reason,
                reject_action=True,
                rules_triggered=rules,
            )

        if verdict == "caution" or score < thresholds["caution_scope_max"]:
            rules.append(
                f"scope_score ({score}) in caution band "
                f"[{thresholds['min_scope_score']}, {thresholds['caution_scope_max']})"
            )
            return PolicyDecision(
                action="caution",
                reason=result.reason,
                must_confirm_with_user=True,
                rules_triggered=rules,
            )

        return PolicyDecision(
            action="approve",
            reason=result.reason,
            rules_triggered=rules,
        )

    def evaluate_completion(self, result: ValidatorResult) -> PolicyDecision:
        thresholds = self._get_thresholds()
        rules: List[str] = []

        if result.score >= thresholds["completion_stop_score"] and result.passed:
            rules.append(f"completion_score == {result.score}")
            return PolicyDecision(
                action="stop",
                reason="Mission appears complete — recommend stopping further work",
                recommend_stopping=True,
                rules_triggered=rules,
            )

        return PolicyDecision(
            action="continue",
            reason=result.reason,
            rules_triggered=rules,
        )

    def scope_verdict(self, score: int, hard_reject: bool = False) -> str:
        thresholds = self._get_thresholds()
        if hard_reject or score < thresholds["min_scope_score"]:
            return "reject"
        if score < thresholds["caution_scope_max"]:
            return "caution"
        return "approve"
