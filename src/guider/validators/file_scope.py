"""File-path scope validation."""

from __future__ import annotations

import re
from typing import List, Optional

from guider.mission.models import Mission, ValidatorResult

OUT_OF_SCOPE_PATH_PATTERNS = [
    r"(^|/)(auth|oauth|login|signup)(/|$)",
    r"(^|/)(migrations?|alembic)(/|$)",
    r"(^|/)docker",
    r"(^|/)k8s",
    r"(^|/)kubernetes",
    r"\.env",
    r"(^|/)infra(/|$)",
]

MVP_FORBIDDEN_PATHS = [
    r"(^|/)backend(/|$)",
    r"(^|/)server(/|$)",
    r"(^|/)api/routes",
]


class FileScopeValidator:
    name = "file_scope_validator"

    def validate(
        self,
        mission: Mission,
        files: List[str],
        allowed_prefixes: Optional[List[str]] = None,
    ) -> ValidatorResult:
        if not files:
            return ValidatorResult(
                name=self.name,
                score=100,
                passed=True,
                reason="No files specified",
            )

        issues: List[str] = []
        score = 100
        is_mvp = any("mvp" in c.lower() or "simple" in c.lower() for c in mission.constraints)

        if len(files) > mission.scope_max_files:
            issues.append(
                f"File count ({len(files)}) exceeds mission budget ({mission.scope_max_files})"
            )
            score -= 30

        for fpath in files:
            normalized = fpath.replace("\\", "/").lstrip("./")

            if allowed_prefixes:
                if not any(normalized.startswith(p.rstrip("/")) for p in allowed_prefixes):
                    issues.append(f"Path outside allowed scope: {normalized}")
                    score -= 25

            for pattern in OUT_OF_SCOPE_PATH_PATTERNS:
                if re.search(pattern, normalized, re.I):
                    issues.append(f"Sensitive/out-of-scope path: {normalized}")
                    score -= 20

            if is_mvp:
                for pattern in MVP_FORBIDDEN_PATHS:
                    if re.search(pattern, normalized, re.I):
                        issues.append(f"MVP-forbidden path: {normalized}")
                        score -= 30

        score = max(0, min(100, score))
        passed = score >= 60 and not any("exceeds" in i or "forbidden" in i for i in issues)

        return ValidatorResult(
            name=self.name,
            score=score,
            passed=passed,
            reason="; ".join(issues) if issues else "All file paths within scope",
            details={"files": files, "issues": issues},
        )
