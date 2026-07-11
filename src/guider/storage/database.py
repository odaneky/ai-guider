from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from guider.config.loader import get_config
from guider.mission.models import (
    Decision,
    DecisionSource,
    Mission,
    MissionEvent,
    MissionEventType,
    MissionStatus,
    PendingQuestion,
    ValidatorResult,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    success_criteria TEXT NOT NULL DEFAULT '[]',
    constraints TEXT NOT NULL DEFAULT '[]',
    unknowns TEXT NOT NULL DEFAULT '[]',
    assumptions TEXT NOT NULL DEFAULT '[]',
    risks TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'planning',
    confidence_score REAL NOT NULL DEFAULT 0.5,
    context TEXT,
    completed_items TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mission_events (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS validator_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT,
    validator_name TEXT NOT NULL,
    score INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    reason TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_questions (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    unknown TEXT NOT NULL,
    question TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    answered INTEGER NOT NULL DEFAULT 0,
    answer TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT,
    tool_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    """Local SQLite storage for missions, events, and decisions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
        if "source" not in cols:
            conn.execute(
                "ALTER TABLE decisions ADD COLUMN source TEXT NOT NULL DEFAULT 'agent_assumption'"
            )
        mcols = {row[1] for row in conn.execute("PRAGMA table_info(missions)").fetchall()}
        if "template_id" not in mcols:
            conn.execute("ALTER TABLE missions ADD COLUMN template_id TEXT")
        if "scope_max_files" not in mcols:
            conn.execute("ALTER TABLE missions ADD COLUMN scope_max_files INTEGER NOT NULL DEFAULT 20")

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _dt_to_str(dt: datetime) -> str:
        return dt.isoformat()

    @staticmethod
    def _str_to_dt(value: str) -> datetime:
        return datetime.fromisoformat(value)

    def save_mission(self, mission: Mission) -> Mission:
        mission.updated_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO missions
                (id, objective, success_criteria, constraints, unknowns, assumptions,
                 risks, status, confidence_score, context, completed_items,
                 template_id, scope_max_files, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission.id,
                    mission.objective,
                    json.dumps(mission.success_criteria),
                    json.dumps(mission.constraints),
                    json.dumps(mission.unknowns),
                    json.dumps(mission.assumptions),
                    json.dumps(mission.risks),
                    mission.status.value,
                    mission.confidence_score,
                    mission.context,
                    json.dumps(mission.completed_items),
                    mission.template_id,
                    mission.scope_max_files,
                    self._dt_to_str(mission.created_at),
                    self._dt_to_str(mission.updated_at),
                ),
            )
        return mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_mission(row)

    def list_missions(self, limit: int = 50) -> List[Mission]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM missions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_mission(row) for row in rows]

    def _row_to_mission(self, row: sqlite3.Row) -> Mission:
        keys = row.keys()
        return Mission(
            id=row["id"],
            objective=row["objective"],
            success_criteria=json.loads(row["success_criteria"]),
            constraints=json.loads(row["constraints"]),
            unknowns=json.loads(row["unknowns"]),
            assumptions=json.loads(row["assumptions"]),
            risks=json.loads(row["risks"]),
            status=MissionStatus(row["status"]),
            confidence_score=row["confidence_score"],
            context=row["context"],
            template_id=row["template_id"] if "template_id" in keys else None,
            scope_max_files=row["scope_max_files"] if "scope_max_files" in keys else 20,
            completed_items=json.loads(row["completed_items"]),
            created_at=self._str_to_dt(row["created_at"]),
            updated_at=self._str_to_dt(row["updated_at"]),
        )

    def record_event(self, event: MissionEvent) -> MissionEvent:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mission_events
                (id, mission_id, event_type, message, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.mission_id,
                    event.event_type.value,
                    event.message,
                    json.dumps(event.metadata),
                    self._dt_to_str(event.created_at),
                ),
            )
        return event

    def list_events(self, mission_id: str, limit: int = 100) -> List[MissionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM mission_events
                WHERE mission_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (mission_id, limit),
            ).fetchall()
        return [
            MissionEvent(
                id=row["id"],
                mission_id=row["mission_id"],
                event_type=MissionEventType(row["event_type"]),
                message=row["message"],
                metadata=json.loads(row["metadata"]),
                created_at=self._str_to_dt(row["created_at"]),
            )
            for row in rows
        ]

    def save_decision(self, decision: Decision) -> Decision:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO decisions
                (id, mission_id, title, description, reason, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.mission_id,
                    decision.title,
                    decision.description,
                    decision.reason,
                    decision.source.value if hasattr(decision.source, "value") else decision.source,
                    self._dt_to_str(decision.created_at),
                ),
            )
        return decision

    def list_decisions(self, mission_id: str) -> List[Decision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE mission_id = ? ORDER BY created_at DESC",
                (mission_id,),
            ).fetchall()
        return [
            Decision(
                id=row["id"],
                mission_id=row["mission_id"],
                title=row["title"],
                description=row["description"],
                reason=row["reason"],
                source=DecisionSource(row["source"]) if "source" in row.keys() else DecisionSource.AGENT_ASSUMPTION,
                created_at=self._str_to_dt(row["created_at"]),
            )
            for row in rows
        ]

    def save_validator_result(
        self, result: ValidatorResult, mission_id: Optional[str] = None
    ) -> ValidatorResult:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO validator_results
                (mission_id, validator_name, score, passed, reason, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    result.name,
                    result.score,
                    int(result.passed),
                    result.reason,
                    json.dumps(result.details),
                    self._dt_to_str(datetime.now(timezone.utc)),
                ),
            )
        return result

    def get_setting(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            mission_count = conn.execute("SELECT COUNT(*) as c FROM missions").fetchone()["c"]
            event_count = conn.execute("SELECT COUNT(*) as c FROM mission_events").fetchone()["c"]
            decision_count = conn.execute("SELECT COUNT(*) as c FROM decisions").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) as c FROM missions WHERE status = 'active'"
            ).fetchone()["c"]
            pending = conn.execute(
                "SELECT COUNT(*) as c FROM pending_questions WHERE answered = 0"
            ).fetchone()["c"]
        return {
            "missions": mission_count,
            "events": event_count,
            "decisions": decision_count,
            "active_missions": active,
            "pending_questions": pending,
            "database_path": str(self.db_path),
        }

    def save_pending_question(self, q: PendingQuestion) -> PendingQuestion:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_questions
                (id, mission_id, unknown, question, severity, answered, answer, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    q.id, q.mission_id, q.unknown, q.question, q.severity,
                    int(q.answered), q.answer, self._dt_to_str(q.created_at),
                ),
            )
        return q

    def list_pending_questions(self, mission_id: str) -> List[PendingQuestion]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_questions WHERE mission_id = ? ORDER BY created_at",
                (mission_id,),
            ).fetchall()
        return [self._row_to_pending(row) for row in rows]

    def get_unanswered_questions(self, mission_id: str) -> List[PendingQuestion]:
        return [q for q in self.list_pending_questions(mission_id) if not q.answered]

    def _row_to_pending(self, row: sqlite3.Row) -> PendingQuestion:
        return PendingQuestion(
            id=row["id"],
            mission_id=row["mission_id"],
            unknown=row["unknown"],
            question=row["question"],
            severity=row["severity"],
            answered=bool(row["answered"]),
            answer=row["answer"],
            created_at=self._str_to_dt(row["created_at"]),
        )

    def set_preference(self, key: str, value: str, reason: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO preferences (key, value, reason, updated_at) VALUES (?, ?, ?, ?)",
                (key, value, reason, self._dt_to_str(datetime.now(timezone.utc))),
            )

    def get_preference(self, key: str) -> Optional[Dict[str, str]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM preferences WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return {"key": row["key"], "value": row["value"], "reason": row["reason"]}

    def list_preferences(self) -> List[Dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM preferences ORDER BY key").fetchall()
        return [{"key": r["key"], "value": r["value"], "reason": r["reason"]} for r in rows]

    def log_tool_call(self, tool_name: str, mission_id: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tool_calls (mission_id, tool_name, created_at) VALUES (?, ?, ?)",
                (mission_id, tool_name, self._dt_to_str(datetime.now(timezone.utc))),
            )

    def count_tool_calls(self, mission_id: Optional[str] = None) -> int:
        with self._connect() as conn:
            if mission_id:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM tool_calls WHERE mission_id = ?",
                    (mission_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()
        return row["c"]

    def list_validator_results(self, mission_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT validator_name, score, passed, reason, created_at
                FROM validator_results WHERE mission_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (mission_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]


_db_instance: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    global _db_instance
    if _db_instance is None or db_path is not None:
        path = db_path or Path(get_config().database_path)
        _db_instance = Database(path)
    return _db_instance


def reset_database_singleton() -> None:
    """Clear singleton — used by tests to avoid touching ~/.ai-guider."""
    global _db_instance
    _db_instance = None
