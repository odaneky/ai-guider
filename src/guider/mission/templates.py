"""Mission templates for common request types."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "mvp-webapp": {
        "name": "MVP Web App",
        "description": "Simple browser-based application, local-first",
        "context_profile": "personal",
        "success_criteria": [
            "Core user workflow works end-to-end",
            "UI is usable on desktop and mobile",
            "Data persists between sessions",
            "No unnecessary backend complexity",
        ],
        "constraints": [
            "Keep MVP simple",
            "Minimum necessary action — avoid scope creep",
            "Prefer local-first unless user specifies otherwise",
        ],
        "scope_max_files": 15,
        "default_unknowns_skip": ["authentication", "user roles"],
    },
    "personal-site": {
        "name": "Personal / Creative Site",
        "description": "Storytelling, portfolio, or couple journey site",
        "context_profile": "personal",
        "success_criteria": [
            "Site communicates the intended story or message",
            "User can browse all main sections",
            "Design feels intentional and personal",
            "Content is easy for the owner to customize",
        ],
        "constraints": [
            "No auth unless explicitly requested",
            "Focus on content and design over infrastructure",
            "Minimum necessary action — avoid scope creep",
        ],
        "scope_max_files": 25,
        "default_unknowns_skip": [
            "authentication",
            "user roles and permissions",
            "compliance requirements",
            "database",
        ],
    },
    "api-service": {
        "name": "API Service",
        "description": "Backend API with clear endpoints",
        "context_profile": "saas",
        "success_criteria": [
            "API endpoints work as documented",
            "Input validation on all endpoints",
            "Errors return meaningful responses",
            "Basic tests cover core endpoints",
        ],
        "constraints": [
            "Keep MVP simple",
            "No premature microservices",
        ],
        "scope_max_files": 30,
        "default_unknowns_skip": [],
    },
    "refactor": {
        "name": "Focused Refactor",
        "description": "Targeted code improvement without scope expansion",
        "context_profile": "internal",
        "success_criteria": [
            "Refactor achieves stated goal without behavior regression",
            "Tests pass after refactor",
            "No unrelated files modified",
        ],
        "constraints": [
            "Refactor only — no new features",
            "Maximum necessary change only",
        ],
        "scope_max_files": 10,
        "default_unknowns_skip": [
            "authentication",
            "deployment environment",
            "technology stack",
        ],
    },
}


def list_templates() -> List[Dict[str, str]]:
    return [
        {"id": tid, "name": t["name"], "description": t["description"]}
        for tid, t in TEMPLATES.items()
    ]


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    return TEMPLATES.get(template_id)
