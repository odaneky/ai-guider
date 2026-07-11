"""Cursor hook runtime: session bootstrap + pre-edit act gate."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from guider.config.loader import get_config
from guider.storage.database import Database, get_database
from guider.workspace import get_active_mission_id, get_workspace_key

ACT_GRANT_PREFIX = "act_grant:"
SESSION_RULE_NAME = "ai-guider-session.mdc"


def _grant_key(workspace: str) -> str:
    return f"{ACT_GRANT_PREFIX}{workspace}"


def record_act_grant(
    db: Database,
    workspace_path: Optional[str],
    *,
    mission_id: str,
    action: str,
    files: Optional[List[str]],
    verdict: str,
    ttl_seconds: Optional[int] = None,
) -> dict:
    """Persist a short-lived permission to edit after govern_request(act)."""
    config = get_config()
    ttl = ttl_seconds if ttl_seconds is not None else config.hooks.grant_ttl_seconds
    workspace = get_workspace_key(workspace_path)
    now = int(time.time())
    grant = {
        "mission_id": mission_id,
        "action": action,
        "files": files or [],
        "verdict": verdict,
        "approved_at": now,
        "expires_at": now + max(60, ttl),
        "workspace": workspace,
    }
    db.set_setting(_grant_key(workspace), json.dumps(grant))
    return grant


def clear_act_grant(db: Database, workspace_path: Optional[str] = None) -> None:
    workspace = get_workspace_key(workspace_path)
    db.set_setting(_grant_key(workspace), "")


def get_act_grant(db: Database, workspace_path: Optional[str] = None) -> Optional[dict]:
    workspace = get_workspace_key(workspace_path)
    raw = db.get_setting(_grant_key(workspace))
    if not raw:
        return None
    try:
        grant = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if int(grant.get("expires_at", 0)) < int(time.time()):
        return None
    return grant


def build_bootstrap_context(
    workspace_path: Optional[str] = None,
    *,
    include_map: bool = True,
    db: Optional[Database] = None,
) -> dict:
    """Build session bootstrap payload for hooks / CLI."""
    from guider.service import GuiderService

    database = db or get_database()
    svc = GuiderService(db=database)
    workspace = get_workspace_key(workspace_path)
    resume = svc.resume_mission(workspace)
    grant = get_act_grant(database, workspace)

    map_summary = None
    if include_map:
        try:
            cmap = svc.map_codebase(workspace, max_depth=3)
            map_summary = {
                "file_count": (cmap.get("summary") or {}).get("file_count"),
                "languages": (cmap.get("summary") or {}).get("languages"),
                "entrypoints": (cmap.get("entrypoints") or [])[:8],
                "hints": (cmap.get("hints") or [])[:5],
                "symbol_sample": list((cmap.get("symbol_index") or {}).keys())[:12],
            }
        except Exception as exc:  # noqa: BLE001 — bootstrap must not crash hooks
            map_summary = {"error": str(exc)}

    text = _format_bootstrap_text(workspace, resume, grant, map_summary)
    return {
        "workspace": workspace,
        "mission": resume,
        "act_grant": grant,
        "map_summary": map_summary,
        "additional_context": text,
        "text": text,
    }


def write_session_rule(context_text: str, rules_dir: Optional[Path] = None) -> Path:
    """Write always-on Cursor rule so bootstrap reaches the agent even if sessionStart drops context."""
    path = rules_dir or (Path.home() / ".cursor" / "rules")
    path.mkdir(parents=True, exist_ok=True)
    rule_path = path / SESSION_RULE_NAME
    body = (
        "---\n"
        "description: AI Guider live session bootstrap (auto-updated)\n"
        "alwaysApply: true\n"
        "---\n\n"
        "# AI Guider Active Session\n\n"
        "This file is refreshed by AI Guider hooks. Prefer it over guessing.\n\n"
        f"{context_text}\n"
    )
    rule_path.write_text(body, encoding="utf-8")
    return rule_path


def _format_bootstrap_text(
    workspace: str,
    resume: dict,
    grant: Optional[dict],
    map_summary: Optional[dict],
) -> str:
    lines = [
        "## AI Guider session bootstrap",
        f"Workspace: `{workspace}`",
    ]
    mid = resume.get("mission_id")
    if not mid:
        lines.extend([
            "No active mission for this workspace.",
            "If the task is non-trivial: call `classify_task` then `govern_request(phase='start')`.",
            "Call `map_codebase` before deep exploration.",
        ])
    else:
        lines.extend([
            f"Active mission: `{mid}`",
            f"Status: {resume.get('status')} · Confidence: {resume.get('confidence_score')}",
            f"Objective: {resume.get('objective')}",
        ])
        pending = resume.get("pending_questions") or {}
        qs = pending.get("questions") or []
        if qs:
            lines.append("Pending questions (ask user, then submit_user_answer):")
            for q in qs[:5]:
                lines.append(f"- {q.get('unknown')}: {q.get('question')}")
        else:
            lines.append("No pending questions — call refine_plan then govern_request(phase='plan').")
        for step in (resume.get("next_steps") or [])[:3]:
            lines.append(f"Next: {step}")

    if grant:
        lines.append(
            f"Act grant active until {grant.get('expires_at')} "
            f"(verdict={grant.get('verdict')}, action={grant.get('action')!r})."
        )
    else:
        lines.append(
            "No act grant — before editing files call "
            "`govern_request(phase='act', action=..., files=[...])`."
        )

    if map_summary and not map_summary.get("error"):
        lines.append("Codebase map (summary):")
        lines.append(f"- Files scanned: {map_summary.get('file_count')}")
        langs = map_summary.get("languages") or {}
        if langs:
            lines.append("- Languages: " + ", ".join(f"{k}={v}" for k, v in list(langs.items())[:6]))
        eps = map_summary.get("entrypoints") or []
        if eps:
            lines.append("- Entrypoints: " + ", ".join(eps[:5]))
        for hint in map_summary.get("hints") or []:
            lines.append(f"- Hint: {hint}")
    elif map_summary and map_summary.get("error"):
        lines.append(f"Codebase map unavailable: {map_summary['error']}")

    return "\n".join(lines)


def evaluate_edit_permission(
    *,
    workspace_path: Optional[str],
    file_path: Optional[str],
    db: Optional[Database] = None,
) -> dict:
    """Decide whether a Write/edit tool call may proceed."""
    config = get_config()
    if not config.hooks.enforce_act:
        return {
            "permission": "allow",
            "reason": "hooks.enforce_act is disabled",
        }

    database = db or get_database()
    workspace = get_workspace_key(workspace_path)
    mission_id = get_active_mission_id(database, workspace)
    if not mission_id:
        return {
            "permission": "allow",
            "reason": "No active mission — edit gate skipped",
        }

    mission = database.get_mission(mission_id)
    if mission is None:
        return {"permission": "allow", "reason": "Active mission missing from DB"}

    unanswered = database.get_unanswered_questions(mission_id)
    if unanswered and config.rules.require_user_confirmation and config.profile != "permissive":
        return {
            "permission": "deny",
            "user_message": "AI Guider: answer pending mission questions before editing.",
            "agent_message": (
                f"Blocked: mission {mission_id} has {len(unanswered)} pending question(s). "
                "Call await_user_input / submit_user_answer before Write."
            ),
            "reason": "pending_questions",
        }

    grant = get_act_grant(database, workspace)
    if not grant:
        return {
            "permission": "deny",
            "user_message": "AI Guider: call govern_request(phase='act') before editing files.",
            "agent_message": (
                f"Blocked: active mission {mission_id} has no act grant. "
                "Call govern_request(phase='act', action='...', files=[...]) and only edit if "
                "quality_gate is proceed or caution (confirm with user on caution)."
            ),
            "reason": "missing_act_grant",
        }

    if grant.get("verdict") == "reject":
        return {
            "permission": "deny",
            "user_message": "AI Guider: last act was rejected.",
            "agent_message": "Blocked: last govern_request(act) was reject. Do not edit.",
            "reason": "act_rejected",
        }

    allowed_files = grant.get("files") or []
    if allowed_files and file_path:
        if not _file_covered(file_path, allowed_files, workspace):
            return {
                "permission": "deny",
                "user_message": "AI Guider: file not in act grant file list.",
                "agent_message": (
                    f"Blocked: `{file_path}` is not in the approved act files {allowed_files}. "
                    "Re-run govern_request(phase='act', files=[...]) including this path."
                ),
                "reason": "file_not_in_grant",
            }

    return {
        "permission": "allow",
        "reason": "act_grant_ok",
        "grant": grant,
    }


def _file_covered(file_path: str, allowed: List[str], workspace: str) -> bool:
    path = Path(file_path)
    candidates = [str(path), path.name]
    try:
        candidates.append(str(path.resolve().relative_to(Path(workspace).resolve())))
    except Exception:
        pass
    for a in allowed:
        a_path = Path(a)
        for c in candidates:
            if c == a or c.endswith(a) or str(path).endswith(a) or a_path.name == path.name:
                return True
            try:
                if path.resolve() == (Path(workspace) / a).resolve():
                    return True
            except Exception:
                continue
    return False


def handle_session_start(payload: Dict[str, Any], db: Optional[Database] = None) -> dict:
    roots = payload.get("workspace_roots") or []
    workspace = roots[0] if roots else None
    boot = build_bootstrap_context(workspace, db=db)
    config = get_config()
    rule_path = None
    if config.hooks.write_session_rule:
        try:
            rule_path = write_session_rule(boot["text"])
        except OSError:
            rule_path = None
    out = {
        "additional_context": boot["additional_context"],
        "env": {
            "AI_GUIDER_WORKSPACE": boot["workspace"],
            "AI_GUIDER_SESSION_BOOTSTRAPPED": "1",
        },
    }
    if rule_path:
        out["env"]["AI_GUIDER_SESSION_RULE"] = str(rule_path)
    return out


def handle_pre_tool_use(payload: Dict[str, Any], db: Optional[Database] = None) -> dict:
    tool = (payload.get("tool_name") or "").strip()
    # Only gate mutating file tools
    if tool not in {"Write", "StrReplace", "Delete", "EditNotebook", "ApplyPatch"}:
        return {"permission": "allow"}

    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            tool_input = {}

    file_path = (
        tool_input.get("path")
        or tool_input.get("file_path")
        or tool_input.get("target_notebook")
    )
    workspace = None
    roots = payload.get("workspace_roots") or []
    if roots:
        workspace = roots[0]
    elif payload.get("cwd"):
        workspace = payload["cwd"]

    try:
        decision = evaluate_edit_permission(
            workspace_path=workspace, file_path=file_path, db=db
        )
    except Exception as exc:  # noqa: BLE001
        # Fail open so a broken hook never bricks editing
        return {
            "permission": "allow",
            "agent_message": f"AI Guider hook error (fail-open): {exc}",
        }

    if decision["permission"] == "allow":
        return {"permission": "allow"}
    return {
        "permission": "deny",
        "user_message": decision.get("user_message"),
        "agent_message": decision.get("agent_message"),
    }


def run_hook_stdin() -> None:
    """CLI entry: read Cursor hook JSON from stdin, write JSON response."""
    import sys

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return

    event = (
        payload.get("hook_event_name")
        or payload.get("event")
        or ""
    ).lower()

    # Infer from argv if event missing
    if len(sys.argv) > 1:
        event = sys.argv[1].lower()

    if event in {"sessionstart", "session_start"}:
        print(json.dumps(handle_session_start(payload)))
    elif event in {"pretooluse", "pre_tool_use"}:
        print(json.dumps(handle_pre_tool_use(payload)))
    else:
        # Default: try session if additional fields look like sessionStart
        if "session_id" in payload or "composer_mode" in payload:
            print(json.dumps(handle_session_start(payload)))
        else:
            print(json.dumps(handle_pre_tool_use(payload)))
