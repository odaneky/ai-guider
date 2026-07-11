# Installation guide

This guide walks you from zero to “AI Guider is connected to my coding agent.”

No prior MCP knowledge needed.

---

## Before you start

### What you need

1. This project on your computer (example path: `~/ai-guider`)
2. **Python 3.10+** installed  
   - Check: `python3 --version`  
   - On Mac, `python3.12` from Homebrew works well
3. At least one AI coding client:
   - [Cursor](https://cursor.com)
   - [Claude Code](https://code.claude.com) and/or Claude Desktop
   - [OpenAI Codex](https://developers.openai.com/codex)

### What “install” means here

AI Guider has two parts:

1. **The Guider program** — runs on your machine (`ai-guider`)
2. **Client wiring** — tells Cursor / Claude / Codex how to talk to Guider (MCP config)

You install (1) once. You run wiring (2) for each client you use.

---

## Part A — Install the Guider program

Open a terminal and run:

```bash
cd ~/ai-guider
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows (PowerShell):**

```powershell
cd ~\ai-guider
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Confirm it works

```bash
ai-guider doctor
```

You want mostly **ok** rows (some **warn** items are fine if you have not connected Cursor yet).

Optional: make `ai-guider` available without activating the venv every time:

```bash
# Example with pipx (installs an isolated copy)
brew install pipx          # if needed
pipx install ~/ai-guider
```

Or add the venv binary to your PATH:

```bash
# macOS/Linux example
export PATH="$HOME/ai-guider/.venv/bin:$PATH"
```

---

## Part B — Connect your AI clients

### Option 1 — Connect everything (simplest)

With the venv active (or `ai-guider` on PATH):

```bash
ai-guider init --all-clients
```

This configures Cursor (with hooks), Claude Code, Claude Desktop, and Codex in one go.

Then restart each app you use (see [After install](#after-install--always-do-this)).

### Option 2 — Connect only what you use

```bash
ai-guider init --cursor --hooks     # Cursor IDE + edit guardrails
ai-guider init --claude             # Claude Code CLI
ai-guider init --claude-desktop     # Claude Desktop chat app
ai-guider init --codex              # OpenAI Codex
```

You can run these commands more than once; Guider updates existing config safely.

### Option 3 — Share Guider with a specific project (Claude Code)

From the project folder:

```bash
ai-guider init --project-mcp .
```

This writes a `.mcp.json` file teammates can use when they open that repo in Claude Code.

---

## After install — always do this

Clients load MCP servers at startup. Config changes do nothing until you refresh:

| Client | Refresh step | How to verify |
|--------|--------------|---------------|
| **Cursor** | Reload Window | Agent tools list includes Guider tools like `govern_request` |
| **Claude Code** | New chat/session | Tools / MCP list shows `ai-guider` |
| **Claude Desktop** | Quit app fully → reopen | Same — Guider tools available |
| **Codex** | Restart Codex | `codex mcp list` shows `ai-guider` |

If tools are missing, see [Troubleshooting](#troubleshooting).

---

## What got created on your machine

| Location | Purpose |
|----------|---------|
| `~/.ai-guider/config.yaml` | Guider settings (profile, hooks, plugins) |
| `~/.ai-guider/guider.db` | Local database (missions, decisions, events) |
| `~/.cursor/mcp.json` | Cursor MCP entry (if `--cursor`) |
| `~/.cursor/rules/ai-guider.mdc` | Cursor workflow rule |
| `~/.cursor/hooks.json` | Cursor hooks (if `--hooks` / `--all-clients`) |
| `~/.claude.json` | Claude Code MCP entry (if `--claude`) |
| Claude Desktop config | Platform-specific path (if `--claude-desktop`) |
| `~/.codex/config.toml` | Codex MCP entry (if `--codex`) |

Details per client: [clients.md](clients.md).

---

## Prefer absolute paths (recommended)

If a client cannot find `ai-guider`, point it at the full binary path. Example on Mac:

```text
/Users/YOURNAME/ai-guider/.venv/bin/ai-guider
```

`ai-guider init` usually detects this automatically. If you install elsewhere, re-run init after moving the project.

---

## Troubleshooting

### `command not found: ai-guider`

Activate the venv first, or use the full path:

```bash
source ~/ai-guider/.venv/bin/activate
which ai-guider
```

### `doctor` says Python is too old

Install Python 3.10+ and recreate the venv with that interpreter.

### Client connected but no Guider tools

1. Confirm init wrote the right config (`ai-guider init --claude` etc.)
2. Fully restart the client (not just a new tab)
3. For Cursor: check **Settings → MCP** that `ai-guider` is enabled
4. For Codex: `codex mcp list`
5. Run `ai-guider doctor` again

### Cursor blocks every file edit

Hooks are enforcing “ask Guider before edit.” Either:

- Have the agent call `govern_request(phase="act", …)` first, or  
- Temporarily disable in `~/.ai-guider/config.yaml`:

```yaml
hooks:
  enforce_act: false
```

Then reload Cursor.

### Claude / Codex ignore Guider workflow

Hooks are Cursor-only today. For Claude and Codex, remind the agent in the prompt:

> Follow AI Guider MCP tools before editing files.

Instructions were also written under `~/.claude/` and `~/.codex/` when you ran init.

---

## Next step

1. Read the **[Usage guide](usage.md)** to run your first governed task  
2. Or jump to **[Clients](clients.md)** if you need another app wired up  

All guides: [docs index](README.md)
