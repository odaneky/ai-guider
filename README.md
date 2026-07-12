# AI Guider

**A local co-pilot for AI coding agents.**

AI Guider does not write your code. It sits beside agents (Cursor, Claude, Codex, and others) and helps them stay on track: clarify what you want, block out-of-scope work, and finish cleanly.

```
You → Cursor / Claude / Codex → AI Guider (local) → decisions, maps, and guardrails
```

Everything stays on your machine. No cloud account required for Guider itself.

---

## What you get

| Capability | In plain terms |
|------------|----------------|
| **Missions** | A clear objective, success criteria, and open questions |
| **Q&A gate** | The agent must ask you before guessing (stack, storage, etc.) |
| **Plan refine** | Sharpens a plan from your answers — does not invent features |
| **Scope checks** | Approve / caution / reject before risky changes |
| **Codebase map** | Quick map of folders, entrypoints, and key symbols |
| **Hooks (Cursor)** | Optional: block file edits until Guider approves the action |

---

## Install in 5 minutes

### Requirements

- macOS, Linux, or Windows
- **Python 3.10 or newer** (3.12 recommended)

### Step 1 — Install AI Guider

```bash
cd ~/ai-guider          # or wherever you cloned this repo
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Check that it works:

```bash
ai-guider doctor
```

### Step 2 — Connect your AI tools

Pick one command:

```bash
# Recommended: connect everything you use
ai-guider init --all-clients

# Or only what you need
ai-guider init --cursor --hooks     # Cursor + edit guardrails
ai-guider init --claude             # Claude Code
ai-guider init --claude-desktop     # Claude Desktop app
ai-guider init --codex              # OpenAI Codex
```

### Step 3 — Restart the client

| Tool | What to do |
|------|------------|
| **Cursor** | Reload window (`Cmd+Shift+P` → “Developer: Reload Window”) |
| **Claude Code** | Start a **new** session |
| **Claude Desktop** | Quit completely, then reopen |
| **Codex** | Restart; run `codex mcp list` and look for `ai-guider` |

Full details: **[Installation guide](docs/installation.md)** · **[Connect Claude & Codex](docs/clients.md)**

---

## How to use it (everyday flow)

You do not need to memorize tool names. Tell your agent:

> Use AI Guider to govern this request:  
> *Build a simple todo webapp, local only, no backend.*

A well-behaved agent will roughly:

1. Start a **mission** and ask you any missing questions  
2. Record your answers  
3. Refine and approve a **plan**  
4. Check **scope** before editing files  
5. Mark success criteria done, then **complete**

Step-by-step with examples: **[Usage guide](docs/usage.md)**

---

## Useful commands

```bash
ai-guider --version       # Installed version
ai-guider help            # Full command guide (what each command does)
ai-guider doctor          # Is my install healthy?
ai-guider bootstrap       # Show active mission + tips for this session
ai-guider map             # Print a map of the current project
ai-guider resume          # What mission is active?
ai-guider missions        # List recent missions
ai-guider report          # Governance summary
ai-guider templates       # Mission templates (personal site, API, …)
```

---

## Documentation

Browse all guides: **[docs/](docs/README.md)**

| Guide | Audience |
|-------|----------|
| [Installation](docs/installation.md) | First-time setup, troubleshooting |
| [Usage](docs/usage.md) | Day-to-day workflow in plain language |
| [Clients (Cursor, Claude, Codex)](docs/clients.md) | Per-app connection steps |
| [Cursor deep dive](docs/cursor-integration.md) | Hooks, maps, Cursor-only features |
| [Publishing to PyPI](docs/publishing.md) | GitHub Release → PyPI workflow |

---

## License

MIT
