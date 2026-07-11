"""Governance reporting and compliance metrics."""

from __future__ import annotations

from typing import Dict, List, Optional

from guider.storage.database import Database


def governance_report(db: Database, mission_id: Optional[str] = None) -> dict:
    """Generate compliance report for a mission or globally."""
    if mission_id:
        return _mission_report(db, mission_id)
    return _global_report(db)


def _mission_report(db: Database, mission_id: str) -> dict:
    mission = db.get_mission(mission_id)
    if not mission:
        return {"error": f"Mission not found: {mission_id}"}

    events = db.list_events(mission_id, limit=500)
    decisions = db.list_decisions(mission_id)
    pending = db.list_pending_questions(mission_id)
    validators = db.list_validator_results(mission_id)

    scope_events = [e for e in events if e.event_type.value == "scope_validated"]
    user_decisions = [d for d in decisions if _decision_source(d) == "user_answer"]
    agent_decisions = [d for d in decisions if _decision_source(d) != "user_answer"]

    scope_approved = sum(
        1 for e in scope_events if e.metadata.get("verdict") == "approve"
    )
    scope_rejected = sum(
        1 for e in scope_events if e.metadata.get("verdict") == "reject"
    )

    tool_calls = db.count_tool_calls(mission_id)
    total_decisions = max(1, len(user_decisions) + len(agent_decisions))
    criteria_total = len(mission.success_criteria)
    criteria_done = len(mission.completed_items)

    return {
        "mission_id": mission_id,
        "objective": mission.objective,
        "status": mission.status.value,
        "confidence_score": mission.confidence_score,
        "completion": {
            "complete": mission.status.value == "completed",
            "criteria_total": criteria_total,
            "criteria_completed": criteria_done,
            "criteria_progress_percent": (
                round(criteria_done / criteria_total * 100, 1) if criteria_total else 0.0
            ),
        },
        "compliance": {
            "total_events": len(events),
            "scope_checks": len(scope_events),
            "scope_approved": scope_approved,
            "scope_rejected": scope_rejected,
            "user_confirmed_decisions": len(user_decisions),
            "agent_assumptions": len(agent_decisions),
            "user_answer_pct": round(len(user_decisions) / total_decisions * 100, 1),
            "agent_assumption_pct": round(len(agent_decisions) / total_decisions * 100, 1),
            "pending_questions": len([p for p in pending if not p.answered]),
            "validator_runs": len(validators),
            "tool_calls_logged": tool_calls,
        },
        "governance_score": _compute_score(
            len(user_decisions), len(agent_decisions),
            scope_rejected, len([p for p in pending if not p.answered]),
        ),
        "recommendations": _recommendations(
            len(user_decisions), len(agent_decisions),
            len([p for p in pending if not p.answered]),
            criteria_total, criteria_done,
        ),
    }


def _global_report(db: Database) -> dict:
    stats = db.get_stats()
    missions = db.list_missions(limit=100)
    return {
        "global": True,
        "stats": stats,
        "missions": [
            {"id": m.id, "objective": m.objective[:60], "status": m.status.value}
            for m in missions
        ],
    }


def _decision_source(decision) -> str:
    src = decision.source
    return src.value if hasattr(src, "value") else str(src)


def _compute_score(user_dec: int, agent_dec: int, rejected: int, pending: int) -> int:
    score = 70
    score += min(20, user_dec * 5)
    score -= min(30, agent_dec * 3)
    score -= rejected * 5
    score -= pending * 10
    return max(0, min(100, score))


def _recommendations(
    user_dec: int,
    agent_dec: int,
    pending: int,
    criteria_total: int = 0,
    criteria_done: int = 0,
) -> List[str]:
    recs = []
    if pending > 0:
        recs.append(f"Answer {pending} pending question(s) via submit_user_answer")
    if agent_dec > user_dec:
        recs.append("Too many agent assumptions — ask user before record_decision")
    if criteria_total and criteria_done < criteria_total:
        recs.append(
            f"Mark {criteria_total - criteria_done} remaining criterion(s) via mark_criterion_complete"
        )
    if not recs:
        recs.append("Governance compliance looks good")
    return recs
