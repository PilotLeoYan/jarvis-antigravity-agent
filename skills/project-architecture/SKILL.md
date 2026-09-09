---
name: project-architecture
description: Deep technical guide on Jarvis Antigravity Agent architecture, lifecycle, bridge loop, and subsystems.
---

# Jarvis Antigravity Agent Architecture

Jarvis Antigravity Agent is an autonomous engineering assistant powered by Google Antigravity CLI (`agy`) connected to Telegram via an asynchronous bridge daemon, featuring local speech-to-text, background subagent orchestration, and automatic self-updates.

## Subsystems

1. **Telegram Bridge Daemon (`src/jarvis_antigravity_agent/main.py`)**:
   - Outbound HTTPS long-polling (`python-telegram-bot`).
   - Dispatches user text and voice messages to handlers.
   - Enforces user authorization via `allowed_users` whitelist.

2. **Execution Engine (`src/jarvis_antigravity_agent/executor.py`)**:
   - Spawns `agy` subprocesses in streaming JSON mode (`--output-format stream-json`).
   - Streams live progress (`_describe_tool`, tool call icons) to Telegram with rate-limited message editing.
   - Preserves session context across sequential prompts via state persistence (`continue_session`).
   - Enforces execution safety timeouts and handles graceful cancellation (`/cancel`).

3. **Subagent Orchestrator (`src/jarvis_antigravity_agent/agent_manager.py`)**:
   - Spawns detached or background `agy` agent instances (`jarvis-spawn-agent`).
   - Delivers autonomous completion alerts back to Telegram chats via `jarvis-send-message`.

4. **MCP Manager (`src/jarvis_antigravity_agent/mcp.py`)**:
   - Inspects and configures Model Context Protocol servers in `~/.gemini/config/mcp_config.json`.
   - Allows Telegram bot commands (`/mcp list`, `/mcp add`, `/mcp remove`) to control agent tool capabilities.

5. **Self-Updater (`src/jarvis_antigravity_agent/updater.py`)**:
   - Detects upstream updates on GitHub repository.
   - Fast-forwards code while strictly protecting local configurations (`config.yaml`, `.env`) and personal data (`state.json`, `cognitive/MEMORY.md`).
   - Triggers clean reload of running daemon.

6. **Offline Speech-to-Text (`src/jarvis_antigravity_agent/stt.py`)**:
   - Local `faster-whisper` (`base` model, `int8` CPU quantization).
   - Zero external API tokens consumed; 100% private.
