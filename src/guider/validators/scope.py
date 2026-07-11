from __future__ import annotations

import re
from typing import List, Optional

from guider.mission.models import Decision, Mission, ValidatorResult
from guider.policies.engine import PolicyEngine

SCOPE_KEYWORDS = {
    "refactor": -30,
    "rewrite": -40,
    "migrate": -20,
    "redesign": -35,
    "optimize": -15,
    "restructure": -25,
    "add feature": -20,
    "nice to have": -40,
    "also": -10,
    "while we're at it": -50,
    "cleanup": -15,
    "improve": -10,
}

OUT_OF_SCOPE_SIGNALS = [
    "oauth",
    "postgresql",
    "postgres",
    "kubernetes",
    "microservice",
    "microservices",
    "deploy to production",
    "authentication system",
    "user authentication",
    "backend api",
    "rest api server",
    "graphql server",
    "redis cluster",
    "docker compose",
    "ci/cd pipeline",
]

LOCAL_MVP_CONSTRAINT_SIGNALS = [
    "mvp",
    "simple",
    "local",
    "no backend",
    "minimum necessary",
]

MISSION_ALIGNMENT_PATTERNS = [
    r"\bimplement\b",
    r"\bbuild\b",
    r"\bcreate\b",
    r"\badd\b",
    r"\bfix\b",
    r"\btest\b",
    r"\bdocument\b",
    r"\bvalidate\b",
    r"\bconfigure\b",
    r"\bstyle\b",
    r"\bpersist\b",
]

DECISION_CONFLICTS = {
    "localstorage": ["postgres", "postgresql", "mysql", "mongodb", "backend", "api server"],
    "html": ["react", "vue", "angular", "next.js", "nextjs"],
    "vanilla javascript": ["react", "vue", "angular", "typescript framework"],
    "no backend": ["oauth", "postgres", "authentication", "api server", "database server"],
}


class ScopeValidator:
    """Determine if a proposed action belongs to the mission."""

    name = "scope_validator"

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def validate(
        self,
        mission: Mission,
        action: str,
        decisions: Optional[List[Decision]] = None,
    ) -> ValidatorResult:
        action_lower = action.lower()
        score = 80
        reasons: List[str] = []
        hard_reject = False
        decisions = decisions or []

        constraint_text = " ".join(mission.constraints).lower()
        context_text = (mission.context or "").lower()
        is_local_mvp = any(
            s in constraint_text or s in context_text for s in LOCAL_MVP_CONSTRAINT_SIGNALS
        )

        objective_words = set(re.findall(r"\b\w{4,}\b", mission.objective.lower()))
        action_words = set(re.findall(r"\b\w{4,}\b", action_lower))
        overlap = objective_words & action_words

        if overlap:
            score += min(15, len(overlap) * 3)
            reasons.append(f"Action shares {len(overlap)} keywords with mission objective")
        else:
            score -= 20
            reasons.append("Action has limited keyword overlap with mission objective")

        for keyword, penalty in SCOPE_KEYWORDS.items():
            if keyword in action_lower:
                score += penalty
                reasons.append(f"Scope creep signal detected: '{keyword}'")

        for criterion in mission.success_criteria:
            criterion_words = set(re.findall(r"\b\w{4,}\b", criterion.lower()))
            if criterion_words & action_words:
                score += 10
                reasons.append(f"Action supports success criterion: {criterion[:50]}")

        if is_local_mvp:
            for signal in OUT_OF_SCOPE_SIGNALS:
                if signal in action_lower:
                    score -= 35
                    hard_reject = True
                    reasons.append(f"Out-of-scope for local MVP: '{signal}'")

        for decision in decisions:
            decision_blob = f"{decision.title} {decision.description}".lower()
            for anchor, conflicts in DECISION_CONFLICTS.items():
                if anchor in decision_blob:
                    for conflict in conflicts:
                        if conflict in action_lower:
                            score -= 40
                            hard_reject = True
                            reasons.append(
                                f"Conflicts with decision '{decision.title}': introduces '{conflict}'"
                            )

        for constraint in mission.constraints:
            if "mvp" in constraint.lower() or "simple" in constraint.lower():
                if any(k in action_lower for k in ["refactor", "rewrite", "redesign", "architecture"]):
                    score -= 25
                    reasons.append("Action may violate MVP simplicity constraint")

        if not any(re.search(p, action_lower) for p in MISSION_ALIGNMENT_PATTERNS):
            score -= 10
            reasons.append("Action does not clearly describe executable work")

        score = max(0, min(100, score))
        verdict = self.policy_engine.scope_verdict(score, hard_reject=hard_reject)
        passed = verdict != "reject"

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason="; ".join(reasons) if reasons else "Action directly supports mission",
            details={
                "action": action,
                "approved": verdict == "approve",
                "verdict": verdict,
                "hard_reject": hard_reject,
            },
        )
