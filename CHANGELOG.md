# Changelog

## 1.0.0

- First stable release
- Local MCP governance for Cursor, Claude Code, Claude Desktop, and Codex
- Missions, Q&A gates, plan refine, scope checks, codebase map, Cursor hooks
- Comprehensive CLI help (`ai-guider help`) and plain-language docs
- Published on PyPI as `ai-guider`

## 0.2.5

- Comprehensive CLI help: `ai-guider help` lists every command and what it does
- `ai-guider help <command>` shows detailed flags; `-h` works alongside `--help`

## 0.2.4

- Documentation rewrite: plain-language installation, usage, and multi-client guides
- New docs/installation.md and docs/README.md index
- GitHub Actions workflow to publish to PyPI on release (`.github/workflows/publish.yml`)
- Package version aligned to 0.2.4

## 0.2.3

- Multi-client setup: Claude Code (`~/.claude.json`), Claude Desktop, OpenAI Codex (`config.toml`)
- `ai-guider init --claude --claude-desktop --codex --all-clients --project-mcp`

## 0.2.2

- Cursor hooks: session bootstrap + pre-edit act grant gate (`ai-guider init --cursor --hooks`)
- `govern_request(act)` records short-lived act grants; Write tools denied without grant when a mission is active
- `ai-guider bootstrap` refreshes live session rule

## 0.2.1

- Codebase map: `map_codebase` MCP tool, `guider://workspace/map` resource, `ai-guider map` CLI
- Structure tree + Python AST symbols on key paths (local-first, no project file writes)

## 0.2.0

- Completion lifecycle: `mark_criterion_complete` / `mark_criteria_complete` MCP tools
- Idempotent `govern_request(start)` reuses similar active missions
- Single confidence boost on decision apply (no double-count)
- Classifier no longer treats short non-trivial requests as trivial
- Plugin scores affect act gates; validators honor `enabled` config
- `MissionSession`, `refine_plan`, `ai-guider resume`, richer active mission resource
- Preference `suggested_answer` on pending questions
- Docs aligned on `submit_user_answer`; report includes user/agent % and criteria progress

## 0.1.0

- Initial MCP governance runtime
