from __future__ import annotations

from typing import List

from guider.mission.models import Mission, ValidatorResult


class CompletionValidator:
    """Determine whether a mission is complete."""

    name = "completion_validator"

    def validate(self, mission: Mission) -> ValidatorResult:
        missing_items: List[str] = []
        score = 100

        for criterion in mission.success_criteria:
            if criterion not in mission.completed_items:
                missing_items.append(criterion)
                score -= max(10, 100 // max(len(mission.success_criteria), 1))

        if mission.unknowns:
            score -= min(30, len(mission.unknowns) * 10)
            missing_items.extend([f"Unresolved unknown: {u}" for u in mission.unknowns])

        score = max(0, score)
        complete = not missing_items and score >= 100

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=complete,
            reason=(
                "All success criteria met"
                if complete
                else f"{len(missing_items)} item(s) remaining"
            ),
            details={
                "complete": complete,
                "missing_items": missing_items,
            },
        )
