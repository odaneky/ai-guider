from __future__ import annotations

from typing import Dict, List, Optional

from guider.mission.models import Mission, MissionStatus


class MissionTracker:
    """Track mission progress and completion state."""

    def get_progress(self, mission: Mission) -> Dict[str, object]:
        total_criteria = len(mission.success_criteria)
        completed = len(mission.completed_items)
        criteria_progress = (
            (completed / total_criteria * 100) if total_criteria > 0 else 0.0
        )

        return {
            "mission_id": mission.id,
            "status": mission.status.value,
            "confidence_score": mission.confidence_score,
            "success_criteria_total": total_criteria,
            "success_criteria_completed": completed,
            "criteria_progress_percent": round(criteria_progress, 1),
            "unknowns_remaining": len(mission.unknowns),
            "assumptions_count": len(mission.assumptions),
            "risks_count": len(mission.risks),
            "is_blocked": mission.status == MissionStatus.BLOCKED,
            "is_complete": mission.status == MissionStatus.COMPLETED,
        }

    def mark_criterion_complete(self, mission: Mission, criterion: str) -> Mission:
        if criterion in mission.success_criteria and criterion not in mission.completed_items:
            mission.completed_items.append(criterion)
        return mission

    def resolve_unknown(self, mission: Mission, unknown: str) -> Mission:
        """Remove an unknown. Confidence boosts are applied by GuiderService."""
        if unknown in mission.unknowns:
            mission.unknowns.remove(unknown)
        return mission

    def add_assumption(self, mission: Mission, assumption: str) -> Mission:
        if assumption not in mission.assumptions:
            mission.assumptions.append(assumption)
        return mission

    def get_state_summary(self, mission: Mission) -> Dict[str, object]:
        progress = self.get_progress(mission)
        return {
            **progress,
            "objective": mission.objective,
            "success_criteria": mission.success_criteria,
            "completed_items": mission.completed_items,
            "constraints": mission.constraints,
            "unknowns": mission.unknowns,
            "assumptions": mission.assumptions,
            "risks": mission.risks,
            "context": mission.context,
        }
