# Architecture & Cognitive Blueprint

This document details the architecture, component interaction, and design decisions behind the **Jarvis Antigravity Agent**.

---

## 1. System Overview

The system bridges **Google Antigravity CLI (`agy`)** with **Telegram** to provide a persistent, autonomous personal assistant that operates entirely on local hardware without incurring per-token API costs from third-party model providers.

```
                              +---------------------------+
                              |   Telegram Bot Servers    |
                              |    (api.telegram.org)     |
                              +-------------+-------------+
                                            ^
                Outbound HTTPS Long Polling |  (Voice notes / Text)
                   (No open firewall ports) v
+-------------------------------------------------------------------------------+
| Host Machine (Linux)                                                          |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | User Systemd Service: agy-telegram.service                              |  |
|  |                                                                         |  |
|  |   +-----------------------+   Audio (.oga)   +------------------------+ |  |
|  |   | Telegram Bot Daemon   | ---------------> | faster-whisper (Local) | |  |
|  |   | (Python 3.10+)        | <--------------- | CPU int8 / 0 Tokens    | |  |
|  |   |                       |  Transcribed Text+------------------------+ |  |
|  |   |                       |                                             |  |
|  |   |                       |   JSON-RPC / CLI  +-----------------------+ |  |
|  |   |                       | ----------------> | Antigravity CLI (agy) | |  |
|  |   |                       | <---------------- | -c / --output-format  | |  |
|  |   |                       |  stream-json out  | Rules: GEMINI.md      | |  |
|  |   +-----------------------+                   | Memory: MEMORY.md     | |  |
|  |                                               | Skills: .agents/skills| |  |
|  |                                               +-----------------------+ |  |
|  +-------------------------------------------------------------------------+  |
|                                                                               |
|  +-----------------------------------+                                        |
|  | send_message.py (CLI Notifier)    | <--- Crons / CI/CD scripts / Pipelines |
|  | Direct Telegram Bot API Delivery  |                                        |
|  +-----------------------------------+                                        |
+-------------------------------------------------------------------------------+
```

---

## 2. Key Architectural Decisions

### 2.1. Zero External API Costs via Google Antigravity CLI
Instead of routing prompts to metered commercial APIs, all reasoning, code manipulation, and tool executions run through Google Antigravity CLI (`agy`) using `--dangerously-skip-permissions` for autonomous local tool execution.

### 2.2. Outbound Long Polling
The bot connects to Telegram using outbound HTTPS long polling. This architecture ensures:
- **Zero Firewall Holes:** No open ports or public static IPs are needed on the host machine.
- **Portability:** Works behind residential NATs, corporate VPNs, and dynamic IPs.

### 2.3. Local Offline Speech-to-Text (`faster-whisper`)
Telegram voice messages and audio files are transcribed locally using `faster-whisper`:
- **Model:** `base` quantized to `int8` on CPU.
- **Latency:** Sub-second to ~1.5s on modern multi-core x86_64 CPUs.
- **Privacy:** Audio data never leaves the host machine.
- **Token Efficiency:** 0 tokens consumed for voice transcription.

### 2.4. Streaming Execution & Live Step Updates
When `agy` processes a request, the bridge listens to the `stream-json` event stream:
1. **Tool Invocations:** Tool calls (`run_command`, `write_to_file`, `view_file`, `grep_search`, `search_web`) are parsed in real time and displayed as live progress items on Telegram (`+ ⚙️ Command`, `+ 📝 Modifying file`).
2. **Intermediate Updates:** Any preparatory text generated before invoking a tool is sent as an immediate conversational update.
3. **Traceability:** The status message is updated to `✅ Completed steps:` upon completion, preserving execution logs.

---

## 3. Cognitive Files & System Prompts

- **`GEMINI.md` / `SOUL.md`:** The core persona definition and operational guardrails injected into the agent's context.
- **`MEMORY.md`:** Long-term external memory tracking system topology, active projects, user preferences, and cron schedules.
- **`skills/`:** Modular capabilities adhering to the Open Agent Skills specification, loaded dynamically into the agent's reasoning framework.
