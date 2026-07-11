from __future__ import annotations

import json

from fastmcp import FastMCP

from guider.service import GuiderService


def register_resources(mcp: FastMCP, service: GuiderService) -> None:
    @mcp.resource("guider://mission/active")
    def active_mission() -> str:
        """Current active mission resume summary for this workspace."""
        return json.dumps(service.resume_mission(), indent=2)

    @mcp.resource("guider://workspace/map")
    def workspace_map() -> str:
        """Codebase structure + key symbols for the active workspace."""
        return json.dumps(service.map_codebase(), indent=2)

    @mcp.resource("guider://mission/{mission_id}/state")
    def mission_state(mission_id: str) -> str:
        """Full state for a mission including policy and decisions."""
        return json.dumps(service.get_mission_state(mission_id), indent=2)

    @mcp.resource("guider://mission/{mission_id}/decisions")
    def mission_decisions(mission_id: str) -> str:
        """Recorded decisions for a mission."""
        decisions = service.db.list_decisions(mission_id)
        return json.dumps(
            [d.model_dump(mode="json") for d in decisions],
            indent=2,
        )

    @mcp.resource("guider://mission/{mission_id}/events")
    def mission_events(mission_id: str) -> str:
        """Recent audit events for a mission."""
        events = service.db.list_events(mission_id, limit=25)
        return json.dumps(
            [e.model_dump(mode="json") for e in events],
            indent=2,
        )
