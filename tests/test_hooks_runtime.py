"""Tests for Cursor hooks runtime (bootstrap + act gate)."""

import json
from pathlib import Path

from guider.hooks_runtime import (
    build_bootstrap_context,
    evaluate_edit_permission,
    handle_pre_tool_use,
    handle_session_start,
    record_act_grant,
    write_session_rule,
)
from guider.service import GuiderService
from guider.storage.database import Database


def test_act_grant_allows_and_denies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AI_GUIDER_WORKSPACE", str(tmp_path))
    db = Database(tmp_path / "h.db")
    svc = GuiderService(db=db)
    mission = svc.create_mission("Build a todo webapp", "MVP local", workspace_path=str(tmp_path))
    for u in list(mission.unknowns):
        svc.submit_user_answer(mission.id, u, "ok")

    denied = evaluate_edit_permission(
        workspace_path=str(tmp_path),
        file_path=str(tmp_path / "index.html"),
        db=db,
    )
    assert denied["permission"] == "deny"

    act = svc.govern_request(
        "todo",
        phase="act",
        mission_id=mission.id,
        action="Create index.html todo UI",
        files=["index.html"],
        workspace_path=str(tmp_path),
    )
    assert act["quality_gate"] in ("proceed", "caution")
    assert act.get("act_grant")

    allowed = evaluate_edit_permission(
        workspace_path=str(tmp_path),
        file_path=str(tmp_path / "index.html"),
        db=db,
    )
    assert allowed["permission"] == "allow"

    other = evaluate_edit_permission(
        workspace_path=str(tmp_path),
        file_path=str(tmp_path / "secrets.env"),
        db=db,
    )
    assert other["permission"] == "deny"


def test_no_mission_allows_edits(tmp_path: Path) -> None:
    db = Database(tmp_path / "empty.db")
    result = evaluate_edit_permission(
        workspace_path=str(tmp_path),
        file_path=str(tmp_path / "a.py"),
        db=db,
    )
    assert result["permission"] == "allow"


def test_bootstrap_and_session_rule(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AI_GUIDER_WORKSPACE", str(tmp_path))
    db = Database(tmp_path / "b.db")
    svc = GuiderService(db=db)
    svc.create_mission("Build a demo app", workspace_path=str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")

    boot = build_bootstrap_context(str(tmp_path), db=db)
    assert "AI Guider session bootstrap" in boot["text"]
    assert boot["mission"]["mission_id"]

    rules = tmp_path / "rules"
    path = write_session_rule(boot["text"], rules_dir=rules)
    assert path.exists()
    assert "Active mission" in path.read_text(encoding="utf-8") or "mission" in path.read_text(
        encoding="utf-8"
    ).lower()


def test_hook_handlers_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AI_GUIDER_WORKSPACE", str(tmp_path))
    db = Database(tmp_path / "c.db")
    out = handle_session_start({"workspace_roots": [str(tmp_path)]}, db=db)
    assert "additional_context" in out
    assert "env" in out

    allow = handle_pre_tool_use(
        {
            "tool_name": "Read",
            "tool_input": {"path": "x"},
            "workspace_roots": [str(tmp_path)],
        },
        db=db,
    )
    assert allow["permission"] == "allow"


def test_record_grant_direct(tmp_path: Path) -> None:
    db = Database(tmp_path / "g.db")
    grant = record_act_grant(
        db,
        str(tmp_path),
        mission_id="mission-x",
        action="edit",
        files=["a.py"],
        verdict="approve",
        ttl_seconds=60,
    )
    assert grant["mission_id"] == "mission-x"
