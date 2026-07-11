from __future__ import annotations

from typing import List

from guider.mission.models import Mission, ValidatorResult


class RiskValidator:
    """Evaluate mission and plan risks."""

    name = "risk_validator"

    HIGH_RISK_KEYWORDS = [
        "production",
        "payment",
        "security",
        "authentication",
        "personal data",
        "pii",
        "compliance",
        "financial",
        "medical",
        "delete",
        "migration",
    ]

    def validate_mission(self, mission: Mission) -> ValidatorResult:
        risks = list(mission.risks)
        score = 100

        objective_lower = mission.objective.lower()
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in objective_lower and not any(keyword in r.lower() for r in risks):
                risks.append(f"Unaddressed risk area: {keyword}")
                score -= 10

        if len(mission.assumptions) > 3:
            risks.append("Multiple unvalidated assumptions increase delivery risk")
            score -= 15

        if mission.confidence_score < 0.5:
            risks.append("Low mission confidence — clarification recommended")
            score -= 20

        score = max(0, score)
        passed = score >= 60

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason=f"Identified {len(risks)} risk factor(s)" if risks else "No significant risks detected",
            details={"risks": risks},
        )

    def validate_plan(self, mission: Mission, plan_steps: List[str]) -> ValidatorResult:
        risks: List[str] = []
        score = 90

        plan_text = " ".join(plan_steps).lower()

        if "test" not in plan_text and any(
            k in mission.objective.lower() for k in ["build", "implement", "create"]
        ):
            risks.append("Plan missing testing steps")
            score -= 15

        if len(plan_steps) > 15:
            risks.append("Plan may be over-engineered — too many steps")
            score -= 20

        if len(plan_steps) < 2 and len(mission.success_criteria) > 2:
            risks.append("Plan may be missing critical steps")
            score -= 25

        dependency_signals = ["first", "then", "after", "before", "depends", "requires"]
        has_dependencies = any(s in plan_text for s in dependency_signals)
        if len(plan_steps) > 5 and not has_dependencies:
            risks.append("Complex plan without explicit dependency ordering")
            score -= 10

        for step in plan_steps:
            if any(k in step.lower() for k in ["refactor", "rewrite", "redesign"]):
                if "mvp" in " ".join(mission.constraints).lower():
                    risks.append(f"Potential over-engineering: {step[:60]}")
                    score -= 10

        score = max(0, score)
        passed = score >= 60

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason="; ".join(risks) if risks else "Plan risk level acceptable",
            details={"risks": risks, "step_count": len(plan_steps)},
        )
