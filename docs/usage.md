# Usage guide

How to work with AI Guider day to day — without drowning in jargon.

---

## The big idea (30 seconds)

When you ask an AI agent to build something vague (“a site for us”, “add auth”, “ship an MVP”), agents often:

- Guess the tech stack  
- Add extras you did not ask for  
- Keep changing scope after you thought you were done  

**AI Guider** makes the agent pause, ask you the important questions, check that each change still matches the mission, and only then claim “done.”

You stay in control. Guider does not invent product ideas for you.

---

## Mental model: a mission

Think of a **mission** as a short project brief Guider keeps for the agent:

| Piece | Meaning |
|-------|---------|
| **Objective** | What you asked for |
| **Success criteria** | How you’ll know it’s finished |
| **Constraints** | Guardrails (“local only”, “no backend”) |
| **Unknowns** | Open questions (stack, storage, timeline…) |
| **Decisions** | Your answers (and sometimes agent assumptions) |

Until unknowns are answered, Guider usually **blocks planning and coding**.

---

## The standard workflow

Use this with **any** connected client (Cursor, Claude, Codex).

### 1. Start with a clear ask

Tell the agent something like:

> Use AI Guider for this.  
> Build a personal photo site for me and my partner — meaningful and simple. I don’t know the stack yet.

### 2. Start a mission

The agent should call tools roughly in this order:

1. `classify_task` — is this big enough to need a mission?  
2. `map_codebase` — if the repo is unfamiliar  
3. `govern_request(phase="start")` **or** `create_mission_from_template(...)`  

**What you should see:** a `mission_id`, a list of questions, and `blocked: true` until you answer.

Tip: For personal/creative sites, `create_mission_from_template("personal-site", …)` asks fewer irrelevant questions (like bank compliance).

### 3. Answer the questions (you, not the agent)

The agent should show you questions from `await_user_input`.

You answer in chat. The agent must call:

```text
submit_user_answer(mission_id, unknown, answer)
```

for **each** answer.

**Do not** let the agent silently “decide” via `record_decision` when Guider asked *you*. That path is for rare agent assumptions and is rejected in strict mode.

Examples of good answers:

- Technology stack → “Vite + React, keep it simple”  
- Data storage → “localStorage / static files only”  
- Timeline → “One evening MVP”

### 4. Refine the plan

After answers are in:

```text
refine_plan(mission_id, draft_steps=[...optional draft...])
```

You get:

- A cleaned objective summary  
- Ordered steps  
- Steps that conflict with your decisions (`out_of_scope`)  
- Anything still missing (`must_ask`)

Then approve the plan:

```text
govern_request(..., phase="plan", plan_steps=[...])
```

### 5. Act — one change at a time

Before implementing a chunk of work:

```text
govern_request(..., phase="act", action="...", files=["path/to/file"])
```

| Result | Meaning |
|--------|---------|
| **proceed** | Safe to implement |
| **caution** | Ask you first, then continue if you agree |
| **reject** | Do **not** implement — change the approach |

Example: if you chose localStorage, “add PostgreSQL + OAuth” should **reject**.

**Cursor tip:** With hooks installed, Write tools may be blocked until a successful `act` grant exists. That’s intentional.

### 6. Finish properly

As criteria are met:

```text
mark_criterion_complete(mission_id, "...")
```

Then:

```text
govern_request(..., phase="complete")
```

If criteria are incomplete, Guider will say so (`blocked` / `continue`) instead of letting the agent fake “all done.”

---

## Everyday helper commands

Run these in your terminal (venv activated):

```bash
ai-guider resume          # What’s the active mission?
ai-guider bootstrap       # Session briefing (mission + map hints)
ai-guider map --json      # Codebase map for the current folder
ai-guider missions        # Recent missions
ai-guider report          # Simple compliance-style summary
ai-guider doctor          # Install health check
```

---

## Codebase map (orientation)

When an agent (or you) is new to a repo:

```bash
ai-guider map --workspace /path/to/project
```

Or via MCP: `map_codebase`.

You get:

- A folder tree (noise like `.venv` skipped)  
- Likely entrypoints (`cli.py`, `mcp/server.py`, …)  
- Key Python symbols  
- Fast lookups: `symbol_index["ClassName"]` → file paths  

It does **not** upload your code anywhere and does **not** write a map file into the project unless you ask for other exports.

---

## Templates (faster starts)

```bash
ai-guider templates
```

Useful ones:

| Template | Good for |
|----------|----------|
| `personal-site` | Portfolios, couple sites, creative pages |
| `mvp-webapp` | Small product MVPs |
| `api-service` | Backend/API work |
| `refactor` | Contained refactors |

---

## Changing direction mid-flight

If you switch stacks (“static HTML → React”) or redesign:

```text
pivot_decision(mission_id, description, reason, new_constraints=[...])
```

Then re-run **plan** (and often **act**) for the new direction.

---

## Scope verdicts — how to read them

| Verdict | What you should do |
|---------|---------------------|
| **approve** / proceed | Let the agent continue |
| **caution** | Read the reason; say yes/no explicitly |
| **reject** | Stop that action; tighten the request or update decisions |

---

## Profiles (strictness)

In `~/.ai-guider/config.yaml`:

```yaml
profile: balanced   # or strict / permissive / light
```

| Profile | Behavior (simplified) |
|---------|------------------------|
| **strict** | Strongest “ask the user” rules |
| **balanced** | Default — good for most work |
| **permissive** | Fewer blocks |
| **light** | Skip full missions for tiny edits |

Hooks:

```yaml
hooks:
  enforce_act: true    # Cursor: require act grant before edits
  grant_ttl_seconds: 1800
```

---

## What Guider stores (privacy)

All mission data is local:

- `~/.ai-guider/guider.db`  
- `~/.ai-guider/config.yaml`  

It does not send your repo to a Guider cloud. Your AI client (Cursor/Claude/Codex) still follows *its* own privacy policy for model calls.

---

## Quick prompt you can paste

```text
Use AI Guider for this task.

1) classify_task and map_codebase if needed
2) govern_request(phase="start") or an appropriate template
3) Ask me every pending question; submit_user_answer for each
4) refine_plan, then govern_request(phase="plan")
5) govern_request(phase="act", files=[...]) before edits
6) mark_criterion_complete as we finish; phase="complete" only when truly done

Do not invent scope. If verdict is reject, stop and explain.
```

---

## Next reading

- [Installation](installation.md) — setup and troubleshooting  
- [Clients](clients.md) — Cursor / Claude / Codex specifics  
- [Cursor integration](cursor-integration.md) — hooks and Cursor-only behavior  
