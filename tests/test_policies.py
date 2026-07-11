"""Tests for policy engine."""

from guider.mission.models import Mission, ValidatorResult
from guider.policies.engine import PolicyEngine


class TestPolicyEngine:
    def setup_method(self) -> None:
        self.engine = PolicyEngine()

    def test_low_confidence_requires_clarification(self) -> None:
        mission = Mission(objective="Vague request", confidence_score=0.4, unknowns=["Auth"])
        decision = self.engine.evaluate_mission(mission)
        assert decision.require_clarification

    def test_high_confidence_proceeds(self) -> None:
        mission = Mission(objective="Clear objective with details", confidence_score=0.85, unknowns=[])
        decision = self.engine.evaluate_mission(mission)
        assert decision.action == "proceed"

    def test_low_scope_rejected(self) -> None:
        result = ValidatorResult(
            name="scope",
            score=40,
            passed=False,
            reason="Out of scope",
            details={"verdict": "reject"},
        )
        decision = self.engine.evaluate_scope(result)
        assert decision.reject_action

    def test_caution_band(self) -> None:
        result = ValidatorResult(
            name="scope",
            score=68,
            passed=True,
            reason="Borderline",
            details={"verdict": "caution"},
        )
        decision = self.engine.evaluate_scope(result)
        assert decision.must_confirm_with_user
        assert not decision.reject_action

    def test_completion_recommends_stopping(self) -> None:
        result = ValidatorResult(name="completion", score=100, passed=True, reason="Done")
        decision = self.engine.evaluate_completion(result)
        assert decision.recommend_stopping
