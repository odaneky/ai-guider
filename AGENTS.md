# AI Guider — Project Governance

**Active mission:** `mission-822a1041`
**Objective:** Create codebase map functionality so AI agents understand the codebase more easily.
**Status:** active · Confidence: 85%

## Success Criteria

- Core functionality works as described in the objective
- User can complete the primary workflow end-to-end
- Solution meets stated constraints
- Users can create new records or entities

## Constraints

- Minimum necessary action — avoid scope creep

## Recorded Decisions

- **Timeline And Deadlines** (user_answer): Next feature slice after 0.2.0 — ship MCP map_codebase + guider://workspace/map with structure + key-path symbols
- **Technology Stack** (user_answer): Stay on current Python AI Guider stack (FastMCP, Pydantic, SQLite). Heuristic filesystem + AST mapping, no LLM.
- **User Roles And Permissions** (user_answer): None — single-user local tool, no roles
- **Authentication** (user_answer): None — local filesystem codebase map only, no auth

## Agent Rules

1. Call `govern_request(phase='act')` before major changes
2. Use `submit_user_answer` for unknowns — do not guess in strict mode
3. If scope verdict is `reject`, do not implement
4. Call `govern_request(phase='complete')` before claiming done
