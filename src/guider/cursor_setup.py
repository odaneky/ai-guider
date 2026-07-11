from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path
from typing import Optional

CURSOR_RULE_CONTENT = """---
description: AI Guider governance workflow for coding and architecture tasks
globs:
alwaysApply: true
---

# AI Guider Workflow

For **coding**, **architecture**, and **research** tasks:

1. `classify_task` — if `requires_mission`, continue
2. `map_codebase` early when unfamiliar with the repo
3. `create_mission_from_template` or `govern_request(phase="start")`
4. `await_user_input` — **ask the user each pending question**
5. `submit_user_answer` for every user response (NOT `record_decision`)
6. `refine_plan` after objective is locked
7. `govern_request(phase="plan")` before editing files
8. `govern_request(phase="act", files=[...])` before major changes
9. `mark_criterion_complete` as success criteria are met
10. `pivot_decision` when user changes direction
11. `export_mission` after creating project files
12. `govern_request(phase="complete")` before claiming done

## Hooks (when installed)

- Session bootstrap injects active mission + map summary (see also `ai-guider-session.mdc`)
- File edits may be **denied** until `govern_request(phase="act")` grants permission
- On deny: call act with the intended action/files, then retry the edit

## Rules

- **Never guess** — if `pending_questions.blocked`, ask the user
- `submit_user_answer` for user responses; `record_decision` only for agent assumptions
- If scope `verdict` is `reject`, do not implement
- If `caution`, confirm with user first
- Use `personal-site` template for couple/personal/creative sites
- Use `symbol_index` / `modules_by_path` from `map_codebase` for fast lookups
"""


def resolve_ai_guider_command() -> str:
    """Find the ai-guider executable path."""
    found = shutil.which("ai-guider")
    if found:
        return found
    venv_candidate = Path.cwd() / ".venv" / "bin" / "ai-guider"
    if venv_candidate.exists():
        return str(venv_candidate.resolve())
    home_venv = Path.home() / "ai-guider" / ".venv" / "bin" / "ai-guider"
    if home_venv.exists():
        return str(home_venv.resolve())
    return "ai-guider"


def _package_hooks_dir() -> Path:
    return Path(__file__).resolve().parents[1].parent / "hooks"


def setup_cursor_hooks(cursor_dir: Optional[Path] = None) -> dict:
    """Install AI Guider hooks into ~/.cursor/hooks.json and ~/.cursor/hooks/."""
    cursor = cursor_dir or Path.home() / ".cursor"
    cursor.mkdir(parents=True, exist_ok=True)
    hooks_dir = cursor / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    src_dir = _package_hooks_dir()
    guider_home = Path.home() / "ai-guider"
    python = guider_home / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(resolve_ai_guider_command()).parent / "python"
    if not python.exists():
        python = Path(shutil.which("python3") or "python3")

    # Standalone hook runner that does not rely on relative ../src
    runner = hooks_dir / "ai_guider_hook.py"
    runner.write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n"
        "import sys\n"
        f"sys.path.insert(0, {str(guider_home / 'src')!r})\n"
        "from guider.hooks_runtime import run_hook_stdin\n"
        "if __name__ == '__main__':\n"
        "    run_hook_stdin()\n",
        encoding="utf-8",
    )
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    session_sh = hooks_dir / "ai-guider-session.sh"
    pretool_sh = hooks_dir / "ai-guider-pretool.sh"
    session_sh.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f'exec "{python}" "{runner}" sessionStart\n',
        encoding="utf-8",
    )
    pretool_sh.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        f'exec "{python}" "{runner}" preToolUse\n',
        encoding="utf-8",
    )
    for script in (session_sh, pretool_sh):
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    hooks_json_path = cursor / "hooks.json"
    if hooks_json_path.exists():
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    else:
        data = {"version": 1, "hooks": {}}

    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})

    def _upsert(event: str, entry: dict) -> None:
        entries = hooks.setdefault(event, [])
        # Remove prior AI Guider entries
        hooks[event] = [
            e
            for e in entries
            if "ai-guider" not in str(e.get("command", ""))
        ]
        hooks[event].append(entry)

    _upsert(
        "sessionStart",
        {"command": "./hooks/ai-guider-session.sh", "timeout": 20},
    )
    _upsert(
        "preToolUse",
        {
            "command": "./hooks/ai-guider-pretool.sh",
            "matcher": "Write|StrReplace|Delete|EditNotebook",
            "timeout": 10,
        },
    )

    hooks_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Keep a copy of package templates for reference
    if src_dir.is_dir():
        for name in ("ai_guider_hook.py", "hooks.json.template"):
            src = src_dir / name
            if src.exists():
                shutil.copy2(src, hooks_dir / f"pkg-{name}")

    return {
        "hooks_json": str(hooks_json_path),
        "hooks_dir": str(hooks_dir),
        "session_hook": str(session_sh),
        "pretool_hook": str(pretool_sh),
        "python": str(python),
    }


def setup_cursor(
    mcp_config_path: Optional[Path] = None,
    rules_path: Optional[Path] = None,
    install_hooks: bool = False,
) -> dict:
    """Write Cursor MCP config and governance rule; optionally install hooks."""
    mcp_path = mcp_config_path or Path.home() / ".cursor" / "mcp.json"
    rule_path = rules_path or Path.home() / ".cursor" / "rules" / "ai-guider.mdc"
    command = resolve_ai_guider_command()

    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.parent.mkdir(parents=True, exist_ok=True)

    if mcp_path.exists():
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    else:
        data = {"mcpServers": {}}

    servers = data.setdefault("mcpServers", {})
    servers["ai-guider"] = {"command": command}

    mcp_path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    rule_path.write_text(CURSOR_RULE_CONTENT, encoding="utf-8")

    result = {
        "mcp_config": str(mcp_path),
        "cursor_rule": str(rule_path),
        "command": command,
    }
    if install_hooks:
        result["hooks"] = setup_cursor_hooks(mcp_path.parent)
    return result
