"""Tests for validators."""

from guider.mission.models import Mission
from guider.validators.assumptions import AssumptionsValidator
from guider.validators.completion import CompletionValidator
from guider.validators.consistency import ConsistencyValidator
from guider.validators.risk import RiskValidator
from guider.validators.scope import ScopeValidator


class TestScopeValidator:
    def setup_method(self) -> None:
        self.validator = ScopeValidator()
        self.mission = Mission(
            objective="Build a vehicle service tracker",
            success_criteria=["Users can create vehicles", "Users can track service history"],
            constraints=["Keep MVP simple"],
        )

    def test_approve_aligned_action(self) -> None:
        result = self.validator.validate(
            self.mission, "Implement vehicle creation endpoint"
        )
        assert result.passed
        assert result.score >= 60

    def test_reject_scope_creep(self) -> None:
        result = self.validator.validate(
            self.mission, "Refactor entire codebase while we're at it"
        )
        assert result.details.get("verdict") in ("reject", "caution")

    def test_reject_backend_for_local_mvp(self) -> None:
        from guider.mission.models import Decision

        mission = Mission(
            objective="Build a todo list webapp",
            constraints=["Keep MVP simple"],
            context="MVP: simple, local, no backend",
        )
        decisions = [
            Decision(
                mission_id="m1",
                title="Data Storage",
                description="localStorage",
                reason="No backend",
            )
        ]
        result = self.validator.validate(
            mission,
            "Add OAuth authentication with PostgreSQL backend",
            decisions,
        )
        assert result.details.get("verdict") == "reject"


class TestAssumptionsValidator:
    def setup_method(self) -> None:
        self.validator = AssumptionsValidator()

    def test_detect_assumptions(self) -> None:
        result = self.validator.validate(
            "We will use PostgreSQL because the user probably wants a relational database"
        )
        assert not result.passed or len(result.details["assumptions"]) > 0

    def test_clean_statement(self) -> None:
        result = self.validator.validate("The mission objective is to build a tracker.")
        assert result.passed


class TestCompletionValidator:
    def setup_method(self) -> None:
        self.validator = CompletionValidator()

    def test_incomplete_mission(self) -> None:
        mission = Mission(
            objective="Build tracker",
            success_criteria=["Create vehicles", "Track history"],
        )
        result = self.validator.validate(mission)
        assert not result.details["complete"]
        assert len(result.details["missing_items"]) == 2

    def test_complete_mission(self) -> None:
        mission = Mission(
            objective="Build tracker",
            success_criteria=["Create vehicles"],
            completed_items=["Create vehicles"],
            unknowns=[],
        )
        result = self.validator.validate(mission)
        assert result.details["complete"]


class TestConsistencyValidator:
    def test_vague_objective(self) -> None:
        validator = ConsistencyValidator()
        mission = Mission(objective="Build")
        result = validator.validate(mission)
        assert not result.passed


class TestRiskValidator:
    def test_plan_without_tests(self) -> None:
        validator = RiskValidator()
        mission = Mission(objective="Build a payment system")
        result = validator.validate_plan(mission, ["Set up database", "Implement API"])
        assert any("test" in r.lower() for r in result.details.get("risks", []))

    def test_overengineered_plan(self) -> None:
        validator = RiskValidator()
        mission = Mission(
            objective="Build MVP app",
            constraints=["Keep MVP simple"],
        )
        steps = [f"Step {i}" for i in range(20)]
        result = validator.validate_plan(mission, steps)
        assert any("over-engineer" in r.lower() for r in result.details.get("risks", []))
