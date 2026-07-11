from __future__ import annotations

from guider.mission.models import Mission, MissionEventType, MissionStatus


class MissionLifecycle:
    """Manage mission status transitions."""

    VALID_TRANSITIONS = {
        MissionStatus.PLANNING: {
            MissionStatus.ACTIVE,
            MissionStatus.BLOCKED,
            MissionStatus.CANCELLED,
        },
        MissionStatus.ACTIVE: {
            MissionStatus.BLOCKED,
            MissionStatus.COMPLETED,
            MissionStatus.CANCELLED,
        },
        MissionStatus.BLOCKED: {
            MissionStatus.ACTIVE,
            MissionStatus.PLANNING,
            MissionStatus.CANCELLED,
        },
        MissionStatus.COMPLETED: set(),
        MissionStatus.CANCELLED: set(),
    }

    def can_transition(self, mission: Mission, target: MissionStatus) -> bool:
        return target in self.VALID_TRANSITIONS.get(mission.status, set())

    def transition(self, mission: Mission, target: MissionStatus, reason: str = "") -> Mission:
        if not self.can_transition(mission, target):
            raise ValueError(
                f"Cannot transition from {mission.status.value} to {target.value}"
            )
        mission.status = target
        return mission

    def activate(self, mission: Mission) -> Mission:
        return self.transition(mission, MissionStatus.ACTIVE)

    def complete(self, mission: Mission) -> Mission:
        return self.transition(mission, MissionStatus.COMPLETED)

    def block(self, mission: Mission) -> Mission:
        return self.transition(mission, MissionStatus.BLOCKED)

    def event_for_transition(self, target: MissionStatus) -> MissionEventType:
        if target == MissionStatus.COMPLETED:
            return MissionEventType.TASK_COMPLETED
        return MissionEventType.STATUS_CHANGED
