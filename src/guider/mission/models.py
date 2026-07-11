from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MissionStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionSource(str, Enum):
    USER_ANSWER = "user_answer"
    AGENT_ASSUMPTION = "agent_assumption"


class MissionEventType(str, Enum):
    CREATED = "mission_created"
    UNKNOWN_DETECTED = "unknown_detected"
    QUESTION_ASKED = "question_asked"
    USER_ANSWERED = "user_answered"
    CONSTRAINT_ADDED = "constraint_added"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    DECISION_RECORDED = "decision_recorded"
    PIVOT_RECORDED = "pivot_recorded"
    TASK_COMPLETED = "task_completed"
    STATUS_CHANGED = "status_changed"
    SCOPE_VALIDATED = "scope_validated"
    COMPLETION_CHECKED = "completion_checked"
    TOOL_CALLED = "tool_called"


class ValidatorResult(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    passed: bool
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    id: str = Field(default_factory=lambda: f"decision-{uuid4().hex[:8]}")
    mission_id: str
    title: str
    description: str
    reason: str
    source: DecisionSource = DecisionSource.AGENT_ASSUMPTION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PendingQuestion(BaseModel):
    id: str = Field(default_factory=lambda: f"question-{uuid4().hex[:8]}")
    mission_id: str
    unknown: str
    question: str
    severity: str = "medium"
    answered: bool = False
    answer: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissionEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"event-{uuid4().hex[:8]}")
    mission_id: str
    event_type: MissionEventType
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: f"mission-{uuid4().hex[:8]}")
    objective: str
    success_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    status: MissionStatus = MissionStatus.PLANNING
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    context: Optional[str] = None
    template_id: Optional[str] = None
    scope_max_files: int = 20
    completed_items: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        self.updated_at = datetime.now(timezone.utc)
