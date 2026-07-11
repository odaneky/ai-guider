# Connect Cursor, Claude, and Codex

AI Guider speaks **MCP** (Model Context Protocol). That means one Guider install can serve many AI apps.

This page is the per-app checklist. For first-time install of Guider itself, start with [installation.md](installation.md).

---

## Choose your path

| If you use… | Run this | Then… |
|-------------|----------|-------|
| Everything | `ai-guider init --all-clients` | Restart each app |
| Cursor only | `ai-guider init --cursor --hooks` | Reload Cursor window |
| Claude Code | `ai-guider init --claude` | New Claude Code session |
| Claude Desktop | `ai-guider init --claude-desktop` | Quit & reopen the app |
| OpenAI Codex | `ai-guider init --codex` | Restart; `codex mcp list` |

Always activate your Guider venv first (or use an absolute path to `ai-guider`):

```bash
source ~/ai-guider/.venv/bin/activate
```

---

## Cursor

### Connect

```bash
ai-guider init --cursor --hooks
```

That updates:

- `~/.cursor/mcp.json` — how Cursor starts Guider  
- `~/.cursor/rules/ai-guider.mdc` — workflow the agent should follow  
- `~/.cursor/hooks.json` — session bootstrap + optional edit gate  

### Activate

1. Command Palette → **Developer: Reload Window**  
2. Open **Settings → MCP** and confirm `ai-guider` is on  
3. In Agent chat, Guider tools should appear (`govern_request`, `map_codebase`, …)

### Cursor-only extras

**Session bootstrap** — when a chat starts, Guider injects the active mission and a short codebase summary (also written to `~/.cursor/rules/ai-guider-session.mdc`).

**Edit gate** — if a mission is active, file writes may be blocked until:

```text
govern_request(phase="act", action="...", files=["..."])
```

succeeds. To turn the gate off:

```yaml
# ~/.ai-guider/config.yaml
hooks:
  enforce_act: false
```

Reload Cursor after changing that.

More detail: [cursor-integration.md](cursor-integration.md).

---

## Claude Code

### Connect (user-wide)

```bash
ai-guider init --claude
```

Writes:

- `~/.claude.json` → `mcpServers.ai-guider`  
- Guidance under `~/.claude/CLAUDE.md` and `~/.claude/AI_GUIDER.md`  

### Connect (one project only)

From the project root:

```bash
ai-guider init --project-mcp .
```

Creates `.mcp.json` in that repo (handy for teams).

### Activate

1. Start a **new** Claude Code session in the project  
2. Confirm MCP tools are available (UI varies by version; look for Guider / `govern_request`)  

### Notes

- Claude Code does **not** use Guider’s Cursor hooks. Governance still works via MCP tools + instructions.  
- Prefer an absolute path to the Guider binary if Claude cannot find `ai-guider` on PATH.

---

## Claude Desktop

### Connect

```bash
ai-guider init --claude-desktop
```

Config file locations:

| OS | Typical path |
|----|----------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### Activate

1. **Fully quit** Claude Desktop (not just close the window)  
2. Open it again  
3. Start a chat and check that Guider tools are listed  

---

## OpenAI Codex

### Connect

```bash
ai-guider init --codex
```

Adds a section to `~/.codex/config.toml`:

```toml
[mcp_servers.ai-guider]
command = "/full/path/to/ai-guider"
enabled = true
```

Also writes `~/.codex/AI_GUIDER.md` with the recommended workflow.

### Activate

```bash
codex mcp list
```

You should see `ai-guider`. Restart Codex if the list is stale.

### Notes

Like Claude Code, Codex uses Guider through **MCP tools**, not Cursor hooks. Paste the [usage prompt](usage.md#quick-prompt-you-can-paste) if the agent skips the workflow.

---

## Same tools on every client

Once connected, the workflow is identical:

```text
classify → map (optional) → start → your answers → refine_plan → plan → act → complete
```

See [usage.md](usage.md) for plain-language steps.

---

## Manual setup (if you prefer editing files)

Use the absolute path from `which ai-guider` after activating the venv.

### Claude Code — `~/.claude.json`

```json
{
  "mcpServers": {
    "ai-guider": {
      "type": "stdio",
      "command": "/Users/YOU/ai-guider/.venv/bin/ai-guider"
    }
  }
}
```

### Codex — `~/.codex/config.toml`

```toml
[mcp_servers.ai-guider]
command = "/Users/YOU/ai-guider/.venv/bin/ai-guider"
enabled = true
startup_timeout_sec = 15
tool_timeout_sec = 120
```

### Cursor — `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "ai-guider": {
      "command": "/Users/YOU/ai-guider/.venv/bin/ai-guider"
    }
  }
}
```

Re-running `ai-guider init …` is usually safer than hand-editing.

---

## Troubleshooting by client

| Symptom | Try this |
|---------|----------|
| Tools missing after init | Restart/reload that client; confirm binary path |
| Codex list empty | `codex mcp list`; check `enabled = true` in config.toml |
| Claude Code no MCP | Confirm `~/.claude.json` (not `settings.json`) has `mcpServers` |
| Cursor hooks not firing | Check `~/.cursor/hooks.json`; reload window; open Hooks output channel |
| Wrong Python / FastMCP errors | Use the project `.venv` binary, not system Python 3.9 |

Still stuck? Run `ai-guider doctor` and fix any **fail** rows first.
