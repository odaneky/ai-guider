from __future__ import annotations

import json
from typing import Optional

from fastmcp import FastMCP

from guider.service import GuiderService


def register_prompts(mcp: FastMCP, service: GuiderService) -> None:
    @mcp.prompt
    def start_mission(request: str, context: str = "") -> str:
        """Kick off governance for a new build or feature request."""
        result = service.govern_request(request, phase="start", context=context or None)
        return (
            "Start mission governance for this request.\n\n"
            f"Request: {request}\n"
            f"Context: {context or 'none'}\n\n"
            f"Governance result:\n{json.dumps(result, indent=2)}\n\n"
            "Follow next_steps exactly. Do not implement until plan phase approves."
        )

    @mcp.prompt
    def check_before_action(action: str, mission_id: str = "") -> str:
        """Validate scope before implementing an action."""
        active = service.get_active_mission()
        resolved_id = mission_id or active.get("mission_id")
        if not resolved_id:
            return "No active mission. Call govern_request(phase='start') first."
        result = service.validate_scope(resolved_id, action)
        return (
            f"Scope check for action: {action}\n\n"
            f"Result:\n{json.dumps(result, indent=2)}\n\n"
            "If verdict is reject, do not proceed. If caution, ask the user first."
        )

    @mcp.prompt
    def close_mission(mission_id: str = "") -> str:
        """Validate mission completion before claiming done."""
        active = service.get_active_mission()
        resolved_id = mission_id or active.get("mission_id")
        if not resolved_id:
            return "No active mission to close."
        result = service.govern_request(
            request="complete mission",
            phase="complete",
            mission_id=resolved_id,
        )
        return (
            "Mission completion check.\n\n"
            f"Result:\n{json.dumps(result, indent=2)}\n\n"
            "Only claim done if quality_gate is stop and completion.complete is true."
        )
