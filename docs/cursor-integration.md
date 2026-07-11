# Cursor integration (deep dive)

This page is for **Cursor** users who want the full Guider experience: MCP tools, rules, session bootstrap, and optional edit hooks.

For Claude or Codex, see [clients.md](clients.md). For the shared workflow, see [usage.md](usage.md).

---

## Quick setup

```bash
source ~/ai-guider/.venv/bin/activate
ai-guider init --cursor --hooks
```

Then: **Developer: Reload Window**.

### What that installs

| Piece | Role |
|-------|------|
| MCP server entry | Lets the agent call Guider tools |
| Rule `ai-guider.mdc` | Reminds the agent of the workflow |
| Hooks | Session briefing + block edits without an `act` grant |
| Live rule `ai-guider-session.mdc` | Refreshed briefing (mission, questions, map hints) |

---

## Recommended agent workflow in Cursor

### 1. Start

```text
govern_request("Build a todo webapp", phase="start", context="MVP, local, no backend")
```

You get a `mission_id`, questions, and next steps. Starting again with a similar ask **reuses** the active mission instead of spawning duplicates.

### 2. Answer questions

```text
await_user_input(mission_id)
# Ask the human each question, then:
submit_user_answer(mission_id, "Technology Stack", "HTML/CSS/JS")
```

Use `submit_user_answer` for user answers. Reserve `record_decision` for rare agent assumptions.

### 3. Refine + plan

```text
refine_plan(mission_id, draft_steps=["Create index.html", "Add CSS", "Todo JS"])
govern_request(..., phase="plan", plan_steps=[...])
```

### 4. Act (required before edits when hooks are on)

```text
govern_request(..., phase="act", action="Implement todo UI", files=["index.html"])
```

- **reject** → do not edit  
- **caution** → ask the user  
- **proceed** → Guider stores a short-lived **act grant**; Write tools are allowed for granted files  

### 5. Complete

```text
mark_criterion_complete(mission_id, "...")
govern_request(..., phase="complete")
```

---

## Hooks explained simply

### Session start

When a new Agent chat begins, Guider builds a short briefing:

- Active mission and status  
- Pending questions  
- Whether an act grant exists  
- Codebase map highlights  

That briefing is injected when possible and always written to:

`~/.cursor/rules/ai-guider-session.mdc`

You can refresh it anytime:

```bash
ai-guider bootstrap
```

### Pre-edit gate

Before `Write` / `StrReplace` / `Delete` / `EditNotebook`:

| Situation | Hook result |
|-----------|-------------|
| No active mission | Allow |
| Active mission, unanswered questions | Deny |
| Active mission, no act grant | Deny — call `phase="act"` first |
| Act grant covers the file | Allow |
| Act grant exists but file not listed | Deny — re-run act with that file |

Disable:

```yaml
# ~/.ai-guider/config.yaml
hooks:
  enforce_act: false
```

Reload Cursor after changing config.

---

## Codebase map in Cursor

```text
map_codebase(workspace_path="/path/to/project")
```

Or open MCP resource `guider://workspace/map`.

Useful fields:

- `entrypoints` — where to start reading  
- `modules_by_path` — symbols in a file  
- `symbol_index` — “where is `GuiderService`?”  
- `fingerprint` — cache key so repeat maps stay fast  

CLI:

```bash
ai-guider map --workspace . --json
```

---

## Active mission helpers

```text
get_active_mission()
set_active_mission(mission_id)
```

CLI: `ai-guider resume`

Override workspace detection:

```bash
export AI_GUIDER_WORKSPACE=/path/to/project
```

---

## Environment variables

| Variable | Meaning |
|----------|---------|
| `AI_GUIDER_CONFIG` | Alternate config file path |
| `AI_GUIDER_WORKSPACE` | Force workspace for active mission / map |

---

## Troubleshooting (Cursor)

| Problem | Fix |
|---------|-----|
| No Guider tools | Settings → MCP → enable `ai-guider`; reload window |
| Hooks not running | Confirm `~/.cursor/hooks.json`; check Hooks output channel |
| Every edit denied | Run `phase="act"` with `files=[...]`, or set `enforce_act: false` |
| Stale mission context | `ai-guider bootstrap` or start a new chat after `resume` |
