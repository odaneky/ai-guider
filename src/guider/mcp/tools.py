from __future__ import annotations

from typing import List, Optional

from fastmcp import FastMCP

from guider.service import GuiderService

MCP_INSTRUCTIONS = """
AI Guider is a local governance runtime for AI agents in Cursor.

## Required workflow

1. classify_task — determine if mission is required
2. map_codebase — call early when unfamiliar with the repo (structure + key symbols)
3. govern_request(phase="start") OR create_mission_from_template
4. await_user_input — get questions for the user
5. submit_user_answer — for EACH user response (not record_decision)
6. refine_plan — after objective is locked (optional draft_steps)
7. govern_request(phase="plan") — before file edits
8. govern_request(phase="act", files=[...]) — before each major action
9. mark_criterion_complete — as success criteria are met
10. govern_request(phase="complete") — before claiming done

## Critical rules

- Use submit_user_answer for user responses — NOT record_decision
- record_decision is for agent assumptions only (rejected in strict mode)
- If pending_questions.blocked is true, ASK the user before proceeding
- pivot_decision when user changes direction (e.g. stack or design overhaul)
- export_mission when project files are created
- Do not claim done until mark_criterion_complete covers success criteria
- Prefer map_codebase / guider://workspace/map before deep file reads on unknown repos.
Use symbol_index / modules_by_path for O(1) "where is X?" lookups.

## Scope verdicts: approve | caution | reject
Use get_active_mission when mission_id is unknown.
""".strip()


def register_tools(mcp: FastMCP, service: GuiderService) -> None:
    @mcp.tool
    def classify_task(request: str) -> dict:
        """Classify a request to determine if full mission governance is required."""
        return service.classify_task(request)

    @mcp.tool
    def govern_request(
        request: str,
        phase: str = "start",
        context: Optional[str] = None,
        mission_id: Optional[str] = None,
        action: Optional[str] = None,
        plan_steps: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        """Orchestrate governance by phase: start, plan, act, or complete."""
        return service.govern_request(
            request=request, phase=phase, context=context,
            mission_id=mission_id, action=action, plan_steps=plan_steps,
            files=files, workspace_path=workspace_path,
        )

    @mcp.tool
    def list_mission_templates() -> dict:
        """List available mission templates (mvp-webapp, personal-site, api-service, refactor)."""
        return {"templates": service.list_mission_templates()}

    @mcp.tool
    def create_mission_from_template(
        template_id: str,
        request: str,
        context: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        """Create a mission from a template with pre-filled criteria and smart unknowns."""
        return service.create_mission_from_template(
            template_id, request, context, workspace_path
        )

    @mcp.tool
    def await_user_input(mission_id: str) -> dict:
        """Get pending questions the agent MUST ask the user. Blocks plan until answered."""
        return service.await_user_input(mission_id)

    @mcp.tool
    def submit_user_answer(mission_id: str, unknown: str, answer: str) -> dict:
        """Record a user-confirmed answer. Use this instead of record_decision for user responses."""
        return service.submit_user_answer(mission_id, unknown, answer)

    @mcp.tool
    def refine_plan(
        mission_id: str,
        draft_steps: Optional[List[str]] = None,
    ) -> dict:
        """Sharpen plan structure after objective is locked. Does not invent features."""
        return service.refine_plan(mission_id, draft_steps)

    @mcp.tool
    def pivot_decision(
        mission_id: str,
        description: str,
        reason: str,
        new_constraints: Optional[List[str]] = None,
    ) -> dict:
        """Record a scope or technology pivot (e.g. static site → React). Re-validates mission."""
        return service.pivot_decision(mission_id, description, reason, new_constraints)

    @mcp.tool
    def create_mission(
        request: str,
        context: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        """Convert a user request into a structured mission."""
        mission = service.create_mission(request, context, workspace_path)
        return mission.model_dump(mode="json")

    @mcp.tool
    def set_active_mission(mission_id: str, workspace_path: Optional[str] = None) -> dict:
        """Bind a mission as active for the current workspace."""
        return service.set_active_mission(mission_id, workspace_path)

    @mcp.tool
    def get_active_mission(workspace_path: Optional[str] = None) -> dict:
        """Get the active mission for the current workspace."""
        return service.get_active_mission(workspace_path)

    @mcp.tool
    def analyze_unknowns(
        request: str,
        context: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> dict:
        """Find missing information with context-aware questions."""
        return service.analyze_unknowns(request, context, mission_id)

    @mcp.tool
    def validate_scope(
        mission_id: str,
        action: str,
        files: Optional[List[str]] = None,
    ) -> dict:
        """Validate action scope. Optionally include file paths for path-level checks."""
        if files:
            return service.validate_scope_with_files(mission_id, action, files)
        return service.validate_scope(mission_id, action)

    @mcp.tool
    def detect_assumptions(statement: str, mission_id: Optional[str] = None) -> dict:
        """Find unsupported assumptions in a statement."""
        return service.detect_assumptions(statement, mission_id)

    @mcp.tool
    def review_plan(mission_id: str, plan_steps: List[str]) -> dict:
        """Evaluate a plan for risks, gaps, and overengineering."""
        return service.review_plan(mission_id, plan_steps)

    @mcp.tool
    def validate_completion(mission_id: str) -> dict:
        """Determine whether the mission is complete."""
        return service.validate_completion(mission_id)

    @mcp.tool
    def mark_criterion_complete(mission_id: str, criterion: str) -> dict:
        """Mark a success criterion complete so phase=complete can finish."""
        return service.mark_criterion_complete(mission_id, criterion)

    @mcp.tool
    def mark_criteria_complete(mission_id: str, criteria: List[str]) -> dict:
        """Mark multiple success criteria complete."""
        return service.mark_criteria_complete(mission_id, criteria)

    @mcp.tool
    def record_decision(
        mission_id: str,
        title: str,
        description: str,
        reason: str,
    ) -> dict:
        """Record an agent assumption. Prefer submit_user_answer for user responses."""
        return service.record_decision(mission_id, title, description, reason)

    @mcp.tool
    def get_mission_state(mission_id: str) -> dict:
        """Retrieve current mission progress, events, decisions, and policy state."""
        return service.get_mission_state(mission_id)

    @mcp.tool
    def export_mission(mission_id: str, project_path: str) -> dict:
        """Export mission to .ai-guider/mission.yaml and AGENTS.md in a project."""
        return service.export_mission(mission_id, project_path)

    @mcp.tool
    def get_governance_report(mission_id: Optional[str] = None) -> dict:
        """Compliance report: scope checks, user vs agent decisions, governance score."""
        return service.get_governance_report(mission_id)

    @mcp.tool
    def save_preference(key: str, value: str, reason: str = "") -> dict:
        """Save a user preference for reuse across missions."""
        return service.save_preference(key, value, reason)

    @mcp.tool
    def map_codebase(
        workspace_path: Optional[str] = None,
        max_depth: int = 4,
        refresh: bool = False,
    ) -> dict:
        """Map workspace structure + key Python symbols for agent orientation."""
        return service.map_codebase(workspace_path, max_depth=max_depth, refresh=refresh)

    @mcp.tool
    def list_preferences() -> dict:
        """List saved user preferences."""
        return service.list_preferences()
