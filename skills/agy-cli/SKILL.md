---
name: agy-cli
description: Orchestration guide, execution modes, model selection, and CLI flags for Google Antigravity CLI (agy).
---

# Antigravity CLI (agy) Guide

Operational reference for running Google Antigravity CLI in autonomous headless and bridge environments.

## Execution Modes

### Non-interactive Print Mode (`-p`)
Executes a single prompt and streams or outputs the result:
```bash
agy --dangerously-skip-permissions -p "Inspect git status and report pending changes"
```

### Session Continuation Mode (`-c`)
Maintains conversation and workspace memory across consecutive invocations:
```bash
agy --dangerously-skip-permissions -c -p "Now summarize the changes in bullet points"
```

### Specific Model Override (`--model`)
Specifies the exact Gemini model variant for execution. Must precede `-p`:
```bash
agy --dangerously-skip-permissions --model "Gemini 3.1 Pro (High)" -p "Perform rigorous architectural analysis"
```

### Structured Streaming Mode (`--output-format stream-json`)
Emits NDJSON events (`step`, `tool`, `result`) parsed in real-time by the Telegram bridge:
```bash
agy --dangerously-skip-permissions --output-format stream-json -p "Run tests"
```

## Fundamental Flags & Options
- `--dangerously-skip-permissions`: Autonomous execution without requiring interactive terminal prompts.
- `--model <name>`: Explicitly select model version (e.g., `Gemini 3.1 Pro (High)`, `gemini-2.5-pro`).
- `--output-format stream-json`: Structured streaming JSON events for programmatic daemons and bridges.
- `-c` / `--continue`: Continue conversation context from the previous session.
- `-p` / `--print`: Non-interactive console print mode.
- `--mode [accept-edits|plan]`: Selects agent operational behavior mode.
