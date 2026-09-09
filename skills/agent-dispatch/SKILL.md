---
name: agent-dispatch
description: Procedures for spawning, orchestrating, and monitoring autonomous background Antigravity subagents from Telegram or CLI.
---

# Antigravity Subagent Dispatch Guide

When executing complex, parallel, or long-running tasks, the primary Jarvis agent can deploy autonomous background `agy` subagents.

## Why Deploy Subagents?

1. **Non-blocking Execution**: The main Telegram chat stays responsive for immediate queries while a heavy task runs asynchronously.
2. **Context Isolation**: Complex explorations or multi-file audits do not contaminate the primary conversational session context.
3. **Parallelism**: Multiple subagents can tackle independent subtasks simultaneously.

## Deploying Subagents via `jarvis-spawn-agent`

From the terminal (or when the primary agent runs a command via tool invocation):

```bash
jarvis-spawn-agent \
  --prompt "Perform thorough security audit of src/ and write report to audit.md" \
  --name "SecurityAuditor" \
  --chat-id 123456789 \
  --working-dir "/path/to/project" \
  --model "Gemini 3.1 Pro (High)"
```

### Options:
- `--prompt`: The explicit, self-contained task instructions for the subagent.
- `--name`: Human-readable identifier for tracking.
- `--chat-id`: Telegram chat ID to receive progress and completion notifications upon finish.
- `--working-dir`: Directory in which the subagent operates (defaults to current working dir).
- `--model`: Model variant to override default settings.

## Direct Telegram Commands
Users can also spawn subagents directly from the Telegram conversation:
- `/boost <prompt>` or `/spawn <prompt>`: Spawns an autonomous background subagent.
- `/agents`: Lists running and recently completed subagents.
- `/killagent <agent-id>`: Aborts an active background subagent.

## Notification Delivery
When a background subagent finishes, it sends its final output or summary directly to the designated Telegram chat using `jarvis-send-message`:
```bash
echo "Task completed successfully" | jarvis-send-message --chat-id <chat_id>
```
