from __future__ import annotations

from typing import Dict

PROFILES: Dict[str, Dict[str, float]] = {
    "strict": {
        "min_confidence_threshold": 0.80,
        "min_scope_score": 75,
        "caution_scope_max": 85,
        "completion_stop_score": 100,
    },
    "balanced": {
        "min_confidence_threshold": 0.70,
        "min_scope_score": 60,
        "caution_scope_max": 75,
        "completion_stop_score": 100,
    },
    "permissive": {
        "min_confidence_threshold": 0.50,
        "min_scope_score": 40,
        "caution_scope_max": 65,
        "completion_stop_score": 90,
    },
    "light": {
        "min_confidence_threshold": 0.55,
        "min_scope_score": 50,
        "caution_scope_max": 70,
        "completion_stop_score": 100,
    },
}


def get_profile(name: str) -> Dict[str, float]:
    return PROFILES.get(name, PROFILES["balanced"])
