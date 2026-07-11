"""Heuristic plan refinement after objective/decisions are locked."""

from __future__ import annotations

import re
from typing import List, Optional

from guider.mission.models import Decision, Mission
from guider.validators.scope import DECISION_CONFLICTS


def refine_plan(
    mission: Mission,
    decisions: List[Decision],
    draft_steps: Optional[List[str]] = None,
) -> dict:
    """Sharpen plan structure from mission state. Does not invent features."""
    refined_objective = _refined_objective(mission, decisions)
    drafts = _dedupe_steps(draft_steps or [])
    ordered = _order_steps(drafts, mission)
    missing = _missing_from_criteria(ordered, mission)
    out_of_scope = _flag_out_of_scope(ordered, decisions)
    must_ask = list(mission.unknowns)

    # Append missing criteria as suggested steps (not invented features)
    suggested = list(ordered)
    for item in missing:
        suggested.append(f"Satisfy criterion: {item}")

    return {
        "mission_id": mission.id,
        "refined_objective": refined_objective,
        "ordered_plan_steps": suggested,
        "draft_steps_used": drafts,
        "missing_from_criteria": missing,
        "out_of_scope": out_of_scope,
        "must_ask": must_ask,
        "constraints": mission.constraints,
        "success_criteria": mission.success_criteria,
        "ready_for_plan_gate": len(must_ask) == 0 and len(out_of_scope) == 0,
        "next_steps": (
            ["Call govern_request(phase='plan', plan_steps=ordered_plan_steps)"]
            if not must_ask
            else ["Call submit_user_answer for remaining unknowns before planning"]
        ),
    }


def _refined_objective(mission: Mission, decisions: List[Decision]) -> str:
    base = mission.objective.strip().rstrip(".")
    bits = []
    for d in decisions[:5]:
        title = (d.title or "").strip()
        desc = (d.description or "").strip()
        if title and desc:
            bits.append(f"{title}: {desc}")
        elif desc:
            bits.append(desc)
    if not bits:
        return base
    summary = "; ".join(bits[:3])
    return f"{base} ({summary})"


def _dedupe_steps(steps: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for step in steps:
        key = re.sub(r"\s+", " ", step.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(step.strip())
    return out


def _order_steps(steps: List[str], mission: Mission) -> List[str]:
    """Prefer setup → implement → test → polish ordering when detectable."""
    buckets = {"setup": [], "implement": [], "test": [], "other": []}
    for step in steps:
        lower = step.lower()
        if any(k in lower for k in ("scaffold", "init", "setup", "create project", "install")):
            buckets["setup"].append(step)
        elif any(k in lower for k in ("test", "spec", "verify", "validate")):
            buckets["test"].append(step)
        elif any(k in lower for k in ("implement", "build", "add", "create", "style", "persist")):
            buckets["implement"].append(step)
        else:
            buckets["other"].append(step)
    ordered = buckets["setup"] + buckets["implement"] + buckets["other"] + buckets["test"]
    return ordered or steps


def _missing_from_criteria(steps: List[str], mission: Mission) -> List[str]:
    joined = " ".join(steps).lower()
    missing = []
    for criterion in mission.success_criteria:
        tokens = [t for t in re.findall(r"[a-z0-9]+", criterion.lower()) if len(t) > 3]
        if not tokens:
            continue
        hits = sum(1 for t in tokens if t in joined)
        if hits < max(1, len(tokens) // 3):
            missing.append(criterion)
    return missing


def _flag_out_of_scope(steps: List[str], decisions: List[Decision]) -> List[dict]:
    flagged = []
    decision_text = " ".join(
        f"{d.title} {d.description}".lower() for d in decisions
    )
    for step in steps:
        lower = step.lower()
        for approved, conflicts in DECISION_CONFLICTS.items():
            if approved in decision_text:
                for conflict in conflicts:
                    if conflict in lower:
                        flagged.append({
                            "step": step,
                            "reason": f"Conflicts with decision favoring '{approved}' ({conflict})",
                        })
                        break
    return flagged
