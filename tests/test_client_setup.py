"""Tests for multi-client MCP setup (Claude + Codex)."""

import json
from pathlib import Path

from guider.client_setup import (
    setup_claude_code,
    setup_claude_desktop,
    setup_clients,
    setup_codex,
    write_project_mcp_json,
)


def test_setup_claude_code(tmp_path: Path) -> None:
    cfg = tmp_path / ".claude.json"
    # Point home-relative paths via monkeypatch of functions' path args
    result = setup_claude_code(claude_json_path=cfg, write_instructions=False)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "ai-guider" in data["mcpServers"]
    assert data["mcpServers"]["ai-guider"]["type"] == "stdio"
    assert "command" in data["mcpServers"]["ai-guider"]
    assert result["client"] == "claude_code"


def test_setup_claude_desktop(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    result = setup_claude_desktop(config_path=cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ai-guider"]["command"]
    assert result["client"] == "claude_desktop"


def test_setup_codex(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "gpt-5"\n', encoding="utf-8")
    result = setup_codex(config_path=cfg)
    text = cfg.read_text(encoding="utf-8")
    assert "[mcp_servers.ai-guider]" in text
    assert "command =" in text
    assert "enabled = true" in text
    # Idempotent
    setup_codex(config_path=cfg)
    assert text.count("[mcp_servers.ai-guider]") == 1 or cfg.read_text(encoding="utf-8").count(
        "[mcp_servers.ai-guider]"
    ) == 1
    assert result["client"] == "codex"


def test_write_project_mcp_json(tmp_path: Path) -> None:
    out = write_project_mcp_json(tmp_path, command="/bin/ai-guider")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mcpServers"]["ai-guider"]["command"] == "/bin/ai-guider"


def test_setup_clients_selective(tmp_path: Path, monkeypatch) -> None:
    # Avoid writing into real home for cursor; only claude/codex via patched paths
    claude_json = tmp_path / "claude.json"
    desktop = tmp_path / "desktop.json"
    codex = tmp_path / "codex.toml"

    from guider import client_setup as cs

    monkeypatch.setattr(cs, "setup_claude_code", lambda **kw: setup_claude_code(claude_json_path=claude_json, write_instructions=False))
    monkeypatch.setattr(cs, "setup_claude_desktop", lambda **kw: setup_claude_desktop(config_path=desktop))
    monkeypatch.setattr(cs, "setup_codex", lambda **kw: setup_codex(config_path=codex))

    report = setup_clients(claude_code=True, claude_desktop=True, codex=True)
    assert "claude_code" in report["clients"]
    assert "claude_desktop" in report["clients"]
    assert "codex" in report["clients"]
    assert claude_json.exists()
    assert desktop.exists()
    assert "[mcp_servers.ai-guider]" in codex.read_text(encoding="utf-8")
