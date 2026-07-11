from __future__ import annotations

from typing import Dict

from guider.mission.models import Mission, ValidatorResult
from guider.plugins.base import GuiderPlugin


class PersonalSitePlugin(GuiderPlugin):
    """Validators and unknown handling for personal/creative sites."""

    name = "personal"
    description = "Personal sites, couple journeys, portfolios"

    def register_validators(self) -> Dict[str, object]:
        return {
            "check_content_readiness": self.check_content_readiness,
            "validate_design_scope": self.validate_design_scope,
        }

    def check_content_readiness(self, mission: Mission, summary: str) -> ValidatorResult:
        score = 80
        issues = []
        lower = summary.lower()

        if "placeholder" in lower and "photo" not in lower:
            issues.append("Content may still be placeholder — confirm with user")
            score -= 15

        if mission.unknowns:
            content_unknowns = [u for u in mission.unknowns if any(
                k in u.lower() for k in ["visual", "content", "photo", "media"]
            )]
            if content_unknowns:
                issues.append(f"Unresolved content unknowns: {content_unknowns}")
                score -= 20

        score = max(0, min(100, score))
        return ValidatorResult(
            name="check_content_readiness",
            score=score,
            passed=score >= 60,
            reason="; ".join(issues) if issues else "Content readiness acceptable",
            details={"issues": issues},
        )

    def validate_design_scope(self, mission: Mission, change: str) -> ValidatorResult:
        score = 85
        issues = []
        lower = change.lower()

        design_signals = ["redesign", "overhaul", "pivot", "rebrand", "new layout"]
        if any(s in lower for s in design_signals):
            if mission.status.value == "active":
                issues.append("Major design change on active mission — confirm with user")
                score -= 20

        infra_signals = ["backend", "database", "auth", "deploy", "ci/cd"]
        if any(s in lower for s in infra_signals):
            issues.append("Infrastructure change on personal site — likely out of scope")
            score -= 35

        score = max(0, min(100, score))
        return ValidatorResult(
            name="validate_design_scope",
            score=score,
            passed=score >= 60,
            reason="; ".join(issues) if issues else "Design scope acceptable",
            details={"change": change},
        )
