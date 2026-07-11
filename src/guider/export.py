"""Mission export and AGENTS.md generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import yaml

from guider.mission.models import Mission
from guider.storage.database import Database


def export_mission_yaml(mission: Mission, db: Database, path: Path) -> Path:
    """Export mission to .ai-guider/mission.yaml in a project."""
    out_dir = path / ".ai-guider"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "mission.yaml"

    decisions = db.list_decisions(mission.id)
    data = {
        "mission_id": mission.id,
        "objective": mission.objective,
        "status": mission.status.value,
        "confidence_score": mission.confidence_score,
        "template_id": mission.template_id,
        "success_criteria": mission.success_criteria,
        "constraints": mission.constraints,
        "unknowns": mission.unknowns,
        "decisions": [
            {
                "title": d.title,
                "description": d.description,
                "reason": d.reason,
                "source": d.source.value if hasattr(d.source, "value") else d.source,
            }
            for d in decisions
        ],
    }
    out_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return out_file


def generate_agents_md(mission: Mission, db: Database, path: Path) -> Path:
    """Write AGENTS.md governance instructions for the project."""
    decisions = db.list_decisions(mission.id)
    agents_file = path / "AGENTS.md"

    lines = [
        "# AI Guider — Project Governance",
        "",
        f"**Active mission:** `{mission.id}`",
        f"**Objective:** {mission.objective}",
        f"**Status:** {mission.status.value} · Confidence: {mission.confidence_score:.0%}",
        "",
        "## Success Criteria",
        "",
    ]
    for c in mission.success_criteria:
        lines.append(f"- {c}")

    lines.extend(["", "## Constraints", ""])
    for c in mission.constraints:
        lines.append(f"- {c}")

    if mission.unknowns:
        lines.extend(["", "## Unresolved Unknowns", ""])
        for u in mission.unknowns:
            lines.append(f"- {u}")

    if decisions:
        lines.extend(["", "## Recorded Decisions", ""])
        for d in decisions:
            src = d.source.value if hasattr(d.source, "value") else d.source
            lines.append(f"- **{d.title}** ({src}): {d.description}")

    lines.extend([
        "",
        "## Agent Rules",
        "",
        "1. Call `govern_request(phase='act')` before major changes",
        "2. Use `submit_user_answer` for unknowns — do not guess in strict mode",
        "3. If scope verdict is `reject`, do not implement",
        "4. Call `govern_request(phase='complete')` before claiming done",
        "",
    ])

    agents_file.write_text("\n".join(lines), encoding="utf-8")
    return agents_file
