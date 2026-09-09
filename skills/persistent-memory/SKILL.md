---
name: persistent-memory
description: Conventions and operational procedures for reading, updating, and maintaining persistent memory in cognitive/MEMORY.md.
---

# Persistent Memory Guide

Jarvis maintains long-term cognitive continuity across sessions and restarts through `cognitive/MEMORY.md`.

## Purpose of Persistent Memory

While conversational context is maintained via `agy -c` within an active session, persistent memory survives:
- Full conversation resets (`/new`).
- Daemon restarts and system reboots.
- Subagent dispatches where isolated context is required.

## Structure of `cognitive/MEMORY.md`

`MEMORY.md` should be concise, structured, and updated proactively whenever important facts or durable preferences are established:

```markdown
# Agent Long-Term Memory

## 1. System Topology & Infrastructure
- Operating System: Ubuntu Linux (x86_64)
- Python environment: uv managed, virtualenv in `.venv`
- Primary workspace: `/home/user/workspace`

## 2. User Directives & Preferences
- Code conventions: Strict typing with Mypy, Ruff formatting (88 chars), pytest for tests.
- Communication style: High density, direct, no conversational filler.
- Default AGY model: Gemini 3.1 Pro (High).

## 3. Active Projects & Repositories
- `jarvis-antigravity-agent`: Autonomous Telegram bridge for Antigravity CLI.
```

## Best Practices
1. **Never dump ephemeral logs**: Only record durable facts, user preferences, and project layouts.
2. **Review periodically**: Read `cognitive/MEMORY.md` when initiating new broad tasks.
3. **Atomic edits**: When updating `MEMORY.md`, edit the relevant subsection without altering unaffected entries.
