---
name: agy-cli
description: Orchestration guide, execution modes, and CLI flags for Google Antigravity CLI (agy).
---

# Antigravity CLI (agy) Guide

Operational reference for running Google Antigravity CLI in headless and automated server environments.

## Execution Modes

### Non-interactive Print Mode (`-p`)
Executes a single prompt and returns the output to standard output:
```bash
agy --dangerously-skip-permissions -p "Inspect open network ports and summarize in bullet points"
```

### Session Continuation Mode (`-c`)
Maintains conversational context across consecutive invocations:
```bash
agy --dangerously-skip-permissions -c -p "Now detail the service running on port 8080"
```

## Fundamental Flags
- `--dangerously-skip-permissions`: Autonomous execution without prompting for manual interactive terminal confirmations.
- `--mode [accept-edits|plan]`: Selects agent execution mode.
- `-p` / `--print`: Non-interactive console output.
- `-c` / `--continue`: Continue conversation history.
- `--output-format stream-json`: Structured streaming JSON events for programmatic daemons and bridges.
