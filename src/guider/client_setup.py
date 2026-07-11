"""Multi-client MCP setup: Claude Code, Claude Desktop, OpenAI Codex."""

from __future__ import annotations

import json
import os
import platform
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from guider.cursor_setup import resolve_ai_guider_command

GUIDER_AGENT_INSTRUCTIONS = """# AI Guider

Local governance MCP for missions, scope checks, and codebase maps.

## Required workflow

1. `classify_task` — if `requires_mission`, continue
2. `map_codebase` early when unfamiliar with the repo
3. `govern_request(phase="start")` or `create_mission_from_template`
4. `await_user_input` → ask the user → `submit_user_answer` for each answer
5. `refine_plan` after the objective is locked
6. `govern_request(phase="plan")` before editing files
7. `govern_request(phase="act", files=[...])` before major changes
8. `mark_criterion_complete` as success criteria are met
9. `govern_request(phase="complete")` before claiming done

## Rules

- Use `submit_user_answer` for user responses — NOT `record_decision`
- If scope `verdict` is `reject`, do not implement
- If `caution`, confirm with the user first
- Prefer `symbol_index` / `modules_by_path` from `map_codebase` for lookups
"""


def mcp_server_entry(command: Optional[str] = None) -> Dict[str, Any]:
    cmd = command or resolve_ai_guider_command()
    return {"command": cmd}


def claude_mcp_server_entry(command: Optional[str] = None) -> Dict[str, Any]:
    """Claude Code prefers an explicit stdio type."""
    entry = mcp_server_entry(command)
    entry["type"] = "stdio"
    return entry


def claude_desktop_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    # Linux
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def setup_claude_code(
    claude_json_path: Optional[Path] = None,
    write_instructions: bool = True,
) -> dict:
    """Register AI Guider in Claude Code user MCP config (~/.claude.json)."""
    path = claude_json_path or (Path.home() / ".claude.json")
    command = resolve_ai_guider_command()

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    servers["ai-guider"] = claude_mcp_server_entry(command)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result: Dict[str, Any] = {
        "client": "claude_code",
        "config": str(path),
        "command": command,
    }

    if write_instructions:
        claude_dir = Path.home() / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        instructions = claude_dir / "AI_GUIDER.md"
        instructions.write_text(GUIDER_AGENT_INSTRUCTIONS, encoding="utf-8")
        # Append pointer into global CLAUDE.md if present, else create a short one
        global_md = claude_dir / "CLAUDE.md"
        marker = "<!-- ai-guider -->"
        pointer = (
            f"\n{marker}\n"
            "## AI Guider\n\n"
            "Use the `ai-guider` MCP tools for mission governance. "
            f"See `{instructions}` for the required workflow.\n"
        )
        if global_md.exists():
            text = global_md.read_text(encoding="utf-8")
            if marker not in text:
                global_md.write_text(text.rstrip() + "\n" + pointer, encoding="utf-8")
        else:
            global_md.write_text(
                "# Claude Code — User Instructions\n" + pointer,
                encoding="utf-8",
            )
        result["instructions"] = str(instructions)
        result["claude_md"] = str(global_md)

    return result


def setup_claude_desktop(
    config_path: Optional[Path] = None,
) -> dict:
    """Register AI Guider in Claude Desktop config."""
    path = config_path or claude_desktop_config_path()
    command = resolve_ai_guider_command()

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    servers["ai-guider"] = mcp_server_entry(command)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return {
        "client": "claude_desktop",
        "config": str(path),
        "command": command,
    }


def setup_codex(
    config_path: Optional[Path] = None,
) -> dict:
    """Register AI Guider in OpenAI Codex ~/.codex/config.toml."""
    path = config_path or (Path.home() / ".codex" / "config.toml")
    command = resolve_ai_guider_command()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = (
        "\n# AI Guider — local governance MCP\n"
        "[mcp_servers.ai-guider]\n"
        f'command = "{command}"\n'
        "enabled = true\n"
        "startup_timeout_sec = 15\n"
        "tool_timeout_sec = 120\n"
    )

    # Replace existing ai-guider table if present
    pattern = re.compile(
        r"\n?# AI Guider[^\n]*\n\[mcp_servers\.ai-guider\][^\[]*",
        re.MULTILINE,
    )
    if pattern.search(existing):
        updated = pattern.sub(block.lstrip("\n"), existing, count=1)
    elif "[mcp_servers.ai-guider]" in existing:
        # Bare table without comment — replace from that header to next section
        pattern2 = re.compile(
            r"\[mcp_servers\.ai-guider\][^\[]*",
            re.MULTILINE,
        )
        updated = pattern2.sub(block.lstrip("\n").lstrip(), existing, count=1)
    else:
        updated = existing.rstrip() + "\n" + block

    path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")

    # AGENTS.md-style guidance next to Codex config
    agents = path.parent / "AI_GUIDER.md"
    agents.parent.mkdir(parents=True, exist_ok=True)
    agents.write_text(GUIDER_AGENT_INSTRUCTIONS, encoding="utf-8")

    return {
        "client": "codex",
        "config": str(path),
        "command": command,
        "instructions": str(agents),
    }


def write_project_mcp_json(
    project_path: Path,
    command: Optional[str] = None,
) -> Path:
    """Write project-root .mcp.json for Claude Code / shared team use."""
    out = project_path / ".mcp.json"
    data = {
        "mcpServers": {
            "ai-guider": claude_mcp_server_entry(command),
        }
    }
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def setup_clients(
    *,
    cursor: bool = False,
    cursor_hooks: bool = False,
    claude_code: bool = False,
    claude_desktop: bool = False,
    codex: bool = False,
    project_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Configure selected MCP clients. Returns a report dict."""
    from guider.cursor_setup import setup_cursor

    report: Dict[str, Any] = {"command": resolve_ai_guider_command(), "clients": {}}

    if cursor or cursor_hooks:
        report["clients"]["cursor"] = setup_cursor(install_hooks=cursor_hooks or cursor)

    if claude_code:
        report["clients"]["claude_code"] = setup_claude_code()

    if claude_desktop:
        report["clients"]["claude_desktop"] = setup_claude_desktop()

    if codex:
        report["clients"]["codex"] = setup_codex()

    if project_path is not None:
        report["project_mcp_json"] = str(
            write_project_mcp_json(project_path, report["command"])
        )

    return report
