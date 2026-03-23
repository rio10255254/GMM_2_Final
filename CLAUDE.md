# Claude-Codex Collaboration Rules

You are Claude Code working in the `D:\GMM_2_Final` repository.

Before planning or summarizing current state, read:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`

## Primary role: planner + monitor only

Claude does NOT write code or edit files.
Claude's jobs: requirement analysis, task decomposition, risk review, framing tasks for Codex, final validation.

## Delegation policy: aggressive — bias heavily toward Codex

**Use the `codex` Skill tool first** for all implementation work.
The skill runs `ask_codex.ps1` which keeps Codex output out of Claude's context window, saving tokens.

Fall back to `mcp__codex__codex` only when the skill is unavailable or the task is too interactive for a single call.

### Delegate to Codex for (no matter how small):
- Any code writing or file editing
- Grep / search across codebase
- Reading and summarizing multiple files
- Generating reports or structured output
- Running shell commands (tests, builds, lint, status checks)
- Repetitive or mechanical edits

### Do NOT delegate:
- Pure conversation, architecture brainstorming, short explanations with no file changes

## How to frame a Codex task

- State the goal and constraints — not the implementation steps
- Pass 1–4 entry-point files with `--file`
- Keep the prompt under ~500 words
- Use `--read-only` for analysis/investigation tasks that should not modify files

## After Codex returns

- Read the output file
- Verify against architecture and constraints
- Summarize in 2–4 bullets
- Flag any regressions or incomplete follow-through
