from __future__ import annotations

from typing import Dict

from guider.mission.models import Mission, ValidatorResult
from guider.plugins.base import GuiderPlugin


class SoftwareEngineeringPlugin(GuiderPlugin):
    """Validators for software engineering missions."""

    name = "software_engineering"
    description = "Code change, architecture, and testing guidance"

    def register_validators(self) -> Dict[str, object]:
        return {
            "review_code_change": self.review_code_change,
            "detect_architecture_issue": self.detect_architecture_issue,
            "check_tests": self.check_tests,
        }

    def review_code_change(self, mission: Mission, change_description: str) -> ValidatorResult:
        score = 85
        issues = []
        lower = change_description.lower()

        if "refactor" in lower and "mvp" in " ".join(mission.constraints).lower():
            issues.append("Refactoring may exceed MVP scope")
            score -= 25

        if len(change_description) > 500:
            issues.append("Large change surface — consider splitting")
            score -= 15

        if "unrelated" in lower or "while" in lower:
            issues.append("Change may include unrelated modifications")
            score -= 20

        score = max(0, min(100, score))
        return ValidatorResult(
            name="review_code_change",
            score=score,
            passed=score >= 60,
            reason="; ".join(issues) if issues else "Code change appears scoped appropriately",
            details={"change_description": change_description},
        )

    def detect_architecture_issue(self, mission: Mission, proposal: str) -> ValidatorResult:
        score = 80
        issues = []
        lower = proposal.lower()

        overengineer_signals = [
            "microservice",
            "event sourcing",
            "cqrs",
            "kubernetes",
            "service mesh",
            "multi-region",
        ]
        for signal in overengineer_signals:
            if signal in lower and "mvp" in " ".join(mission.constraints).lower():
                issues.append(f"Potential over-engineering: {signal}")
                score -= 15

        if "database" not in lower and "data" in mission.objective.lower():
            issues.append("Architecture proposal lacks data layer consideration")
            score -= 10

        score = max(0, min(100, score))
        return ValidatorResult(
            name="detect_architecture_issue",
            score=score,
            passed=score >= 60,
            reason="; ".join(issues) if issues else "Architecture proposal acceptable",
            details={"proposal": proposal},
        )

    def check_tests(self, mission: Mission, plan_or_summary: str) -> ValidatorResult:
        score = 70
        issues = []
        lower = plan_or_summary.lower()

        if "test" not in lower and "spec" not in lower:
            issues.append("No testing mentioned in plan or summary")
            score -= 30

        if "unit test" not in lower and "integration" not in lower:
            issues.append("Test strategy unclear — specify unit or integration tests")
            score -= 15

        score = max(0, min(100, score))
        return ValidatorResult(
            name="check_tests",
            score=score,
            passed=score >= 60,
            reason="; ".join(issues) if issues else "Testing coverage addressed",
            details={"summary": plan_or_summary},
        )
