from __future__ import annotations

import os
import re
from typing import List, Optional

# Maps decision titles (normalized) to unknown labels they resolve
DECISION_UNKNOWN_MAP = {
    "technology stack": ["technology stack"],
    "tech stack": ["technology stack"],
    "timeline": ["timeline and deadlines"],
    "data storage": ["database"],
    "database": ["database"],
    "authentication": ["authentication"],
    "auth": ["authentication"],
    "deployment": ["deployment environment"],
    "compliance": ["compliance requirements"],
    "performance": ["performance requirements"],
    "integration": ["integration requirements"],
    "budget": ["budget constraints"],
    "user roles": ["user roles and permissions"],
}

TRIVIAL_PATTERNS = [
    r"\btypo\b",
    r"\bformat\b",
    r"\blint\b",
    r"\bcomment\b",
    r"\brename\b",
    r"\bwhitespace\b",
    r"\bspelling\b",
    r"\bfix lint\b",
]

CODING_PATTERNS = [
    r"\bbuild\b",
    r"\bcreate\b",
    r"\bimplement\b",
    r"\badd\b",
    r"\bdevelop\b",
    r"\bwebapp\b",
    r"\bapplication\b",
    r"\bapi\b",
    r"\bcomponent\b",
    r"\boauth\b",
    r"\bauth\b",
    r"\blogin\b",
    r"\bmvp\b",
    r"\bpayment\b",
    r"\bship\b",
    r"\bfeature\b",
]

ARCHITECTURE_PATTERNS = [
    r"\barchitect\b",
    r"\bdesign\b",
    r"\brefactor\b",
    r"\bmigrate\b",
    r"\brestructure\b",
    r"\bmicroservice\b",
]

RESEARCH_PATTERNS = [
    r"\bresearch\b",
    r"\binvestigate\b",
    r"\banalyze\b",
    r"\bcompare options\b",
    r"\bliterature\b",
]


def classify_task(request: str) -> dict:
    """Classify a request to determine governance requirements."""
    lower = request.lower()

    if any(re.search(p, lower) for p in TRIVIAL_PATTERNS):
        category = "trivial"
        requires_mission = False
    elif any(re.search(p, lower) for p in ARCHITECTURE_PATTERNS):
        category = "architecture"
        requires_mission = True
    elif any(re.search(p, lower) for p in RESEARCH_PATTERNS):
        category = "research"
        requires_mission = True
    elif any(re.search(p, lower) for p in CODING_PATTERNS):
        category = "coding"
        requires_mission = True
    else:
        # Default to general governance — never treat short requests as trivial
        # solely based on word count.
        category = "general"
        requires_mission = True

    return {
        "category": category,
        "requires_mission": requires_mission,
        "recommendation": (
            "Use govern_request(phase='start') before implementation"
            if requires_mission
            else "Light profile: mission optional for trivial edits"
        ),
    }


def match_unknowns_for_decision(title: str) -> List[str]:
    """Return unknown labels resolved by a decision title."""
    key = title.strip().lower()
    matched: List[str] = []
    for pattern, unknowns in DECISION_UNKNOWN_MAP.items():
        if pattern in key:
            matched.extend(unknowns)
    return list(dict.fromkeys(matched))


def objectives_similar(a: str, b: str, threshold: float = 0.35) -> bool:
    """Return True if two objectives share enough meaningful tokens."""
    stop = {"a", "an", "the", "to", "for", "and", "or", "of", "in", "on", "with", "my"}
    ta = {w for w in re.findall(r"[a-z0-9]+", a.lower()) if w not in stop and len(w) > 1}
    tb = {w for w in re.findall(r"[a-z0-9]+", b.lower()) if w not in stop and len(w) > 1}
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    return overlap >= threshold
