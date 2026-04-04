# Project Working Rules

You are Claude Code working in this repository.

Before planning or summarizing current state, read:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`

## Primary role

Claude may analyze requirements, edit files, run shell commands, and verify results directly in this repository.

## Tooling policy

- Prefer direct work in the current session.
- Do not assume any external delegation tool is available.
- Only use external delegation when the user explicitly asks for it and the tool is confirmed to exist.
- If an external delegation path is unavailable, continue the task directly instead of blocking.

## Execution standards

- Keep changes scoped to the request.
- Run relevant checks before reporting completion.
- Summarize the outcome with enough detail for the user to understand what changed and why; call out any remaining risks.
