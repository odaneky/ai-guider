from __future__ import annotations

import re
from typing import List, Tuple

from guider.mission.models import ValidatorResult

ASSUMPTION_PATTERNS: List[Tuple[str, str, int]] = [
    (r"\b(probably|likely|assume|assuming|should be|must be)\b", "hedging language", 2),
    (r"\bthe user (wants|needs|prefers)\b", "unspecified user preference", 3),
    (r"\b(we will use|using|let's use)\s+(\w+)", "technology choice without confirmation", 3),
    (r"\b(postgres|postgresql|mysql|mongodb|react|vue|angular|django|fastapi)\b", "technology assumption", 2),
    (r"\b(by default|standard approach|best practice)\b", "implicit standard", 2),
    (r"\b(everyone|users always|typically)\b", "generalization", 2),
    (r"\b(should|will need to|has to)\b", "unvalidated requirement", 1),
    (r"\bwithout (asking|confirming|checking)\b", "skipped validation", 3),
]

SEVERITY_MAP = {1: "low", 2: "medium", 3: "high"}


class AssumptionsValidator:
    """Find unsupported assumptions in statements."""

    name = "assumptions_validator"

    def validate(self, statement: str) -> ValidatorResult:
        assumptions: List[dict] = []
        total_severity = 0

        for pattern, label, severity_weight in ASSUMPTION_PATTERNS:
            matches = re.finditer(pattern, statement, re.IGNORECASE)
            for match in matches:
                excerpt = self._extract_excerpt(statement, match.start(), match.end())
                assumptions.append({
                    "text": excerpt,
                    "label": label,
                    "severity": SEVERITY_MAP.get(severity_weight, "medium"),
                })
                total_severity += severity_weight

        unique_assumptions = self._deduplicate(assumptions)
        count = len(unique_assumptions)
        score = max(0, 100 - count * 15 - total_severity * 5)
        passed = count == 0 or score >= 70

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason=(
                f"Found {count} unsupported assumption(s)"
                if count
                else "No unsupported assumptions detected"
            ),
            details={"assumptions": unique_assumptions, "statement": statement},
        )

    def _extract_excerpt(self, text: str, start: int, end: int, window: int = 40) -> str:
        excerpt_start = max(0, start - window)
        excerpt_end = min(len(text), end + window)
        excerpt = text[excerpt_start:excerpt_end].strip()
        if excerpt_start > 0:
            excerpt = "..." + excerpt
        if excerpt_end < len(text):
            excerpt = excerpt + "..."
        return excerpt

    def _deduplicate(self, assumptions: List[dict]) -> List[dict]:
        seen = set()
        result = []
        for a in assumptions:
            key = a["text"].lower()
            if key not in seen:
                seen.add(key)
                result.append(a)
        return result
