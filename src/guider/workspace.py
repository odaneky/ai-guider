from __future__ import annotations

import os
from typing import Optional

ACTIVE_MISSION_PREFIX = "active_mission:"


def get_workspace_key(workspace_path: Optional[str] = None) -> str:
    """Resolve workspace identifier for active mission binding."""
    path = (
        workspace_path
        or os.environ.get("AI_GUIDER_WORKSPACE")
        or os.environ.get("CURSOR_WORKSPACE")
        or os.getcwd()
    )
    return os.path.abspath(path)


def _setting_key(workspace_key: str) -> str:
    return f"{ACTIVE_MISSION_PREFIX}{workspace_key}"


def set_active_mission(db, mission_id: str, workspace_path: Optional[str] = None) -> str:
    """Bind a mission as active for the current workspace."""
    workspace_key = get_workspace_key(workspace_path)
    db.set_setting(_setting_key(workspace_key), mission_id)
    return workspace_key


def get_active_mission_id(db, workspace_path: Optional[str] = None) -> Optional[str]:
    """Get active mission id for workspace, if set."""
    workspace_key = get_workspace_key(workspace_path)
    return db.get_setting(_setting_key(workspace_key))


def clear_active_mission(db, workspace_path: Optional[str] = None) -> None:
    workspace_key = get_workspace_key(workspace_path)
    db.set_setting(_setting_key(workspace_key), "")
