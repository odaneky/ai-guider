"""Health checks and diagnostics for AI Guider setup."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import List, Tuple

from guider.config.loader import get_config, get_config_path
from guider.storage.database import get_database


def run_doctor() -> Tuple[bool, List[dict]]:
    """Run all health checks. Returns (all_ok, results)."""
    results: List[dict] = []

    # Python version
    py_ok = sys.version_info >= (3, 10)
    results.append({
        "check": "Python version",
        "status": "ok" if py_ok else "fail",
        "detail": f"{sys.version_info.major}.{sys.version_info.minor} (need 3.10+)",
    })

    # Config
    config_path = get_config_path()
    config_ok = config_path.exists()
    results.append({
        "check": "Config file",
        "status": "ok" if config_ok else "warn",
        "detail": str(config_path),
    })

    # Database
    try:
        db = get_database()
        stats = db.get_stats()
        results.append({
            "check": "Database",
            "status": "ok",
            "detail": f"{stats['database_path']} ({stats['missions']} missions)",
        })
    except Exception as e:
        results.append({"check": "Database", "status": "fail", "detail": str(e)})

    # ai-guider command
    cmd = shutil.which("ai-guider")
    venv_cmd = Path.cwd() / ".venv" / "bin" / "ai-guider"
    home_venv = Path.home() / "ai-guider" / ".venv" / "bin" / "ai-guider"
    if cmd:
        cmd_detail = cmd
        cmd_ok = True
    elif venv_cmd.exists():
        cmd_detail = str(venv_cmd.resolve())
        cmd_ok = True
    elif home_venv.exists():
        cmd_detail = str(home_venv.resolve())
        cmd_ok = True
    else:
        cmd_detail = "Not found — run: pip install -e ."
        cmd_ok = False
    results.append({
        "check": "ai-guider command",
        "status": "ok" if cmd_ok else "fail",
        "detail": cmd_detail,
    })

    # Cursor MCP config
    mcp_path = Path.home() / ".cursor" / "mcp.json"
    mcp_ok = False
    mcp_detail = "Not configured"
    if mcp_path.exists():
        import json
        try:
            data = json.loads(mcp_path.read_text())
            if "ai-guider" in data.get("mcpServers", {}):
                mcp_ok = True
                mcp_detail = str(mcp_path)
            else:
                mcp_detail = f"{mcp_path} exists but ai-guider not listed"
        except Exception:
            mcp_detail = f"{mcp_path} invalid JSON"
    results.append({
        "check": "Cursor MCP config",
        "status": "ok" if mcp_ok else "warn",
        "detail": mcp_detail,
    })

    # Cursor rule
    rule_path = Path.home() / ".cursor" / "rules" / "ai-guider.mdc"
    results.append({
        "check": "Cursor governance rule",
        "status": "ok" if rule_path.exists() else "warn",
        "detail": str(rule_path) if rule_path.exists() else "Run: ai-guider init --cursor",
    })

    # Profile
    try:
        cfg = get_config()
        results.append({
            "check": "Active profile",
            "status": "ok",
            "detail": cfg.profile,
        })
    except Exception as e:
        results.append({"check": "Active profile", "status": "fail", "detail": str(e)})

    all_ok = all(r["status"] != "fail" for r in results)
    return all_ok, results
