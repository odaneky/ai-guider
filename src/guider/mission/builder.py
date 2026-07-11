from __future__ import annotations

import re
from typing import List, Optional

from guider.mission.models import Mission, MissionStatus

# Domain keywords that signal missing information when not specified
UNKNOWN_PATTERNS = {
    "authentication": [
        r"\bauth\b",
        r"\blogin\b",
        r"\buser\b",
        r"\baccount\b",
        r"\bapp\b",
        r"\bapplication\b",
        r"\bsystem\b",
        r"\bplatform\b",
        r"\bapi\b",
        r"\bweb\b",
        r"\bmobile\b",
        r"\bbank\b",
    ],
    "database": [
        r"\bapp\b",
        r"\bsystem\b",
        r"\btracker\b",
        r"\bstore\b",
        r"\bdata\b",
        r"\bplatform\b",
        r"\bapi\b",
    ],
    "deployment environment": [
        r"\bapp\b",
        r"\bsystem\b",
        r"\bdeploy\b",
        r"\bproduction\b",
        r"\bplatform\b",
    ],
    "user roles and permissions": [
        r"\bapp\b",
        r"\bsystem\b",
        r"\bplatform\b",
        r"\badmin\b",
        r"\buser\b",
        r"\bteam\b",
    ],
    "compliance requirements": [
        r"\bbank\b",
        r"\bfinance\b",
        r"\bhealth\b",
        r"\bmedical\b",
        r"\bpayment\b",
        r"\bhipaa\b",
        r"\bgdpr\b",
        r"\bpci\b",
    ],
    "technology stack": [
        r"\bbuild\b",
        r"\bcreate\b",
        r"\bdevelop\b",
        r"\bimplement\b",
        r"\bapp\b",
        r"\bsystem\b",
    ],
    "performance requirements": [
        r"\bscale\b",
        r"\bhigh.?traffic\b",
        r"\bproduction\b",
        r"\benterprise\b",
    ],
    "integration requirements": [
        r"\bintegrat\b",
        r"\bconnect\b",
        r"\bthird.?party\b",
        r"\bapi\b",
    ],
    "timeline and deadlines": [
        r"\bbuild\b",
        r"\bcreate\b",
        r"\bdeliver\b",
        r"\bproject\b",
        r"\bmvp\b",
    ],
    "budget constraints": [
        r"\benterprise\b",
        r"\bproduction\b",
        r"\bscale\b",
    ],
}

SUCCESS_CRITERIA_TEMPLATES = [
    "Core functionality works as described in the objective",
    "User can complete the primary workflow end-to-end",
    "Solution meets stated constraints",
]

RISK_TEMPLATES = {
    "banking": ["Regulatory compliance gaps", "Security vulnerabilities"],
    "finance": ["Regulatory compliance gaps", "Data integrity risks"],
    "health": ["HIPAA compliance", "Patient data security"],
    "scale": ["Performance bottlenecks", "Infrastructure costs"],
    "mvp": ["Scope creep beyond MVP boundaries"],
}


class MissionBuilder:
    """Convert user requests into structured missions."""

    def build(self, request: str, context: Optional[str] = None) -> Mission:
        objective = self._extract_objective(request)
        unknowns = self._detect_unknowns(request, context)
        success_criteria = self._derive_success_criteria(request)
        constraints = self._derive_constraints(request)
        risks = self._derive_risks(request)
        confidence = self._calculate_confidence(unknowns, request)

        return Mission(
            objective=objective,
            success_criteria=success_criteria,
            constraints=constraints,
            unknowns=unknowns,
            assumptions=[],
            risks=risks,
            status=MissionStatus.PLANNING,
            confidence_score=confidence,
            context=context,
        )

    def _extract_objective(self, request: str) -> str:
        cleaned = request.strip()
        cleaned = re.sub(r"^(please|can you|could you|i want to|i need to)\s+", "", cleaned, flags=re.I)
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned[0].upper() + cleaned[1:] if cleaned else "Undefined objective"

    def _detect_unknowns(self, request: str, context: Optional[str] = None) -> List[str]:
        combined = f"{request} {context or ''}".lower()
        unknowns: List[str] = []

        for unknown, patterns in UNKNOWN_PATTERNS.items():
            if any(re.search(p, combined) for p in patterns):
                if not self._is_specified(unknown, combined):
                    unknowns.append(unknown.title() if unknown[0].islower() else unknown)

        if len(request.split()) < 5:
            unknowns.append("Detailed requirements and acceptance criteria")

        return list(dict.fromkeys(unknowns))

    def _is_specified(self, unknown: str, text: str) -> bool:
        specifications = {
            "authentication": [
                r"\boauth\b",
                r"\bjwt\b",
                r"\bsso\b",
                r"\bpassword\b",
                r"\bauth0\b",
                r"\bkeycloak\b",
            ],
            "database": [
                r"\bpostgres\b",
                r"\bmysql\b",
                r"\bmongo\b",
                r"\bsqlite\b",
                r"\bredis\b",
                r"\bdynamodb\b",
            ],
            "deployment environment": [
                r"\baws\b",
                r"\bgcp\b",
                r"\bazure\b",
                r"\bdocker\b",
                r"\bkubernetes\b",
                r"\bon.?prem\b",
                r"\blocal\b",
            ],
            "user roles and permissions": [
                r"\badmin\b",
                r"\brole\b",
                r"\brbac\b",
                r"\bpermission\b",
            ],
            "compliance requirements": [
                r"\bhipaa\b",
                r"\bgdpr\b",
                r"\bpci\b",
                r"\bsoc2\b",
                r"\bcompliance\b",
            ],
            "technology stack": [
                r"\bpython\b",
                r"\btypescript\b",
                r"\breact\b",
                r"\bnode\b",
                r"\brust\b",
                r"\bgo\b",
                r"\bjava\b",
            ],
            "performance requirements": [
                r"\b\d+\s*(req|request|user|rps)\b",
                r"\blatency\b",
                r"\bms\b",
                r"\bconcurrent\b",
            ],
            "integration requirements": [
                r"\bstripe\b",
                r"\bslack\b",
                r"\bwebhook\b",
                r"\brest\b",
                r"\bgraphql\b",
            ],
            "timeline and deadlines": [
                r"\b\d+\s*(day|week|month)\b",
                r"\bdeadline\b",
                r"\basap\b",
                r"\bq[1-4]\b",
            ],
            "budget constraints": [
                r"\bbudget\b",
                r"\bcost\b",
                r"\b\$",
                r"\bfree\b",
                r"\bopen.?source\b",
            ],
        }
        patterns = specifications.get(unknown.lower(), [])
        return any(re.search(p, text) for p in patterns)

    def _derive_success_criteria(self, request: str) -> List[str]:
        criteria = list(SUCCESS_CRITERIA_TEMPLATES)
        lower = request.lower()

        if "track" in lower or "monitor" in lower:
            criteria.append("Users can view and update tracked items")
        if "create" in lower or "add" in lower:
            criteria.append("Users can create new records or entities")
        if "search" in lower or "find" in lower:
            criteria.append("Users can search and filter results")
        if "report" in lower or "analytics" in lower:
            criteria.append("Reports or analytics are available")

        return list(dict.fromkeys(criteria))[:6]

    def _derive_constraints(self, request: str) -> List[str]:
        constraints: List[str] = []
        lower = request.lower()

        if "mvp" in lower or "simple" in lower or "minimal" in lower:
            constraints.append("Keep MVP simple")
        if "local" in lower or "offline" in lower:
            constraints.append("Must run locally without cloud dependencies")
        if "no cloud" in lower:
            constraints.append("No cloud infrastructure required")

        if not constraints:
            constraints.append("Minimum necessary action — avoid scope creep")

        return constraints

    def _derive_risks(self, request: str) -> List[str]:
        risks: List[str] = []
        lower = request.lower()

        for keyword, templates in RISK_TEMPLATES.items():
            if keyword in lower:
                risks.extend(templates)

        if "refactor" in lower:
            risks.append("Unnecessary refactoring expanding scope")

        return list(dict.fromkeys(risks))

    def _calculate_confidence(self, unknowns: List[str], request: str) -> float:
        base = 0.85
        base -= len(unknowns) * 0.08
        if len(request.split()) < 8:
            base -= 0.1
        return max(0.1, min(1.0, round(base, 2)))
