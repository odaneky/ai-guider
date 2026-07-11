from __future__ import annotations

from typing import List

from guider.mission.models import Mission, ValidatorResult


class ConsistencyValidator:
    """Check internal consistency of mission definitions."""

    name = "consistency_validator"

    def validate(self, mission: Mission) -> ValidatorResult:
        issues: List[str] = []
        score = 100

        if not mission.objective or len(mission.objective) < 10:
            issues.append("Objective is too vague or missing")
            score -= 30

        if not mission.success_criteria:
            issues.append("No success criteria defined")
            score -= 25

        overlap = set(mission.unknowns) & set(mission.assumptions)
        if overlap:
            issues.append(f"Items appear as both unknowns and assumptions: {overlap}")
            score -= 20

        if mission.confidence_score > 0.8 and len(mission.unknowns) > 3:
            issues.append("High confidence despite many unresolved unknowns")
            score -= 15

        if "simple" in " ".join(mission.constraints).lower() and len(mission.success_criteria) > 8:
            issues.append("Too many success criteria for a simple/MVP mission")
            score -= 10

        score = max(0, score)
        passed = score >= 70

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason="Mission is internally consistent" if passed else "; ".join(issues),
            details={"issues": issues},
        )
