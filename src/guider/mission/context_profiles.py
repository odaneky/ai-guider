"""Context-aware unknown profiles for different project types."""

from __future__ import annotations

from typing import Dict, List

# Unknowns to SKIP for each context profile (not relevant)
SKIP_UNKNOWNS: Dict[str, List[str]] = {
    "personal": [
        "authentication",
        "user roles and permissions",
        "compliance requirements",
        "performance requirements",
        "budget constraints",
    ],
    "saas": [],
    "internal": [
        "compliance requirements",
        "budget constraints",
    ],
}

# Additional unknowns to ADD per profile
ADD_UNKNOWNS: Dict[str, List[str]] = {
    "personal": [
        "Visual style and mood",
        "Content sections and story structure",
        "Photo and media assets",
    ],
    "saas": [
        "Pricing model",
        "Multi-tenancy requirements",
    ],
    "internal": [
        "Existing system integration points",
    ],
}

# Question templates per profile-specific unknown
PROFILE_QUESTIONS: Dict[str, Dict[str, List[str]]] = {
    "personal": {
        "visual style and mood": [
            "What visual style do you want (minimal, romantic, bold, Pinterest-like)?",
            "Any color preferences or sites you like as inspiration?",
        ],
        "content sections and story structure": [
            "What main sections should the site have (timeline, gallery, letter)?",
            "Is there a narrative arc you want to tell?",
        ],
        "photo and media assets": [
            "Do you have photos ready to include?",
            "Should we use placeholders until you add images?",
        ],
    },
}


def filter_unknowns(unknowns: List[str], profile: str) -> List[str]:
    """Remove irrelevant unknowns for a context profile."""
    skip = [s.lower() for s in SKIP_UNKNOWNS.get(profile, [])]
    filtered = [u for u in unknowns if u.lower() not in skip]
    for extra in ADD_UNKNOWNS.get(profile, []):
        if extra not in filtered:
            filtered.append(extra)
    return filtered


def get_profile_questions(unknown: str, profile: str) -> List[str]:
    key = unknown.lower()
    profile_qs = PROFILE_QUESTIONS.get(profile, {})
    for pattern, qs in profile_qs.items():
        if pattern in key:
            return qs
    return [f"Can you clarify: {unknown}?"]


def detect_profile(request: str, context: str = "", template_profile: str = "") -> str:
    if template_profile:
        return template_profile
    combined = f"{request} {context}".lower()
    personal_signals = [
        "couple", "girlfriend", "boyfriend", "love", "journey", "personal",
        "portfolio", "wedding", "story", "memories", "our ",
    ]
    saas_signals = ["saas", "subscription", "billing", "multi-tenant", "enterprise"]
    if any(s in combined for s in personal_signals):
        return "personal"
    if any(s in combined for s in saas_signals):
        return "saas"
    return "internal"
