# Jarvis Antigravity Agent

> **Autonomous AI Engineering & Research Assistant powered by Google Antigravity CLI (`agy`) with Telegram Bridge & Offline Speech-to-Text.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)](https://core.telegram.org/bots)
[![Speech-to-Text](https://img.shields.io/badge/STT-faster--whisper%20(int8)-orange)](https://github.com/SYSTRAN/faster-whisper)
[![Engine](https://img.shields.io/badge/Core-Google%20Antigravity%20CLI-purple)]()

---

## Overview

**Jarvis Antigravity Agent** is a full-stack, autonomous AI system designed for software engineers, systems programmers, and machine learning researchers.

Instead of incurring ongoing per-token API costs from third-party commercial LLM providers, this architecture connects the local terminal power of **Google Antigravity CLI (`agy`)** to a mobile **Telegram** interface via an outbound HTTPS long-polling daemon.

### Key Highlights
- **Zero External API Costs:** Executes through your native Google Antigravity CLI (`agy`) environment with autonomous tool permissions (`--dangerously-skip-permissions`).
- **Private Offline Speech-to-Text:** Direct transcription of Telegram voice notes using local `faster-whisper` (`base` model, `int8` CPU quantization) — completely free, offline, and private.
- **Zero Inbound Firewall Holes:** Operates via outbound long polling (`api.telegram.org`). No reverse proxies, public IP addresses, or exposed network ports required.
- **Live Execution Streaming:** Streams `stream-json` events from `agy` in real time, presenting tool invocations directly in Telegram.
- **Persistent Cognitive Core:** Governed by explicit behavioral directives (`GEMINI.md` / `SOUL.md`), external persistent memory (`MEMORY.md`), and modular agent skills.
- **Curated Generic Skills:** Packed with 12 battle-tested skills for deep learning research, TDD, merge reconciliation, and debugging.

---

## Architecture

```
                              +---------------------------+
                              |   Telegram Bot Servers    |
                              |    (api.telegram.org)     |
                              +-------------+-------------+
                                            ^
                Outbound HTTPS Long Polling |  (Voice notes / Text)
                   (No open firewall ports) v
+-------------------------------------------------------------------------------+
| Host Linux Machine                                                            |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | User Systemd Service: agy-telegram.service                              |  |
|  |                                                                         |  |
|  |   +-----------------------+   Audio (.oga)   +------------------------+ |  |
|  |   | Telegram Bot Daemon   | --------------> | faster-whisper (Local) | |  |
|  |   | (Python 3.10+)        | <-------------- | CPU int8 / 0 Tokens    | |  |
|  |   |                       |  Transcribed Text+------------------------+ |  |
|  |   |                       |                                             |  |
|  |   |                       |   JSON-RPC / CLI  +-----------------------+ |  |
|  |   |                       | ----------------> | Antigravity CLI (agy) | |  |
|  |   |                       | <---------------- | --output-format       | |  |
|  |   |                       |  stream-json out  | Rules: GEMINI.md      | |  |
|  |   +-----------------------+                   | Memory: MEMORY.md     | |  |
|  |                                               | Skills: .agents/skills| |  |
|  |                                               +-----------------------+ |  |
|  +-------------------------------------------------------------------------+  |
|                                                                               |
|  +-----------------------------------+                                        |
|  | jarvis-send-message (CLI Tool)    | <--- Crons / Scripts / Audit Pipelines|
|  | Direct Telegram Bot API Delivery  |                                        |
|  +-----------------------------------+                                        |
+-------------------------------------------------------------------------------+
```

---

## Repository Structure

```
jarvis-antigravity-agent/
├── README.md                          # Project documentation
├── LICENSE                            # MIT License
├── pyproject.toml                     # Build system & dependencies
├── requirements.txt                   # Python runtime dependencies
├── setup.sh                           # Automated installation script
├── config.json                        # Runtime configuration (gitignored)
├── config.example.json                # Configuration template
├── systemd/
│   └── agy-telegram.service           # User systemd service unit template
├── src/
│   └── jarvis_antigravity_agent/      # Main Python package
│       ├── __init__.py                # Package entrypoint
│       ├── constants.py               # All magic values and tunable parameters
│       ├── messages.py                # All user-facing strings (translations file)
│       ├── config.py                  # Config/state loading and authorization
│       ├── utils.py                   # Message splitting and Telegram helpers
│       ├── stt.py                     # Speech-to-text (faster-whisper) module
│       ├── executor.py                # AGY process execution engine
│       ├── handlers.py                # Telegram command and message handlers
│       ├── notifier.py                # CLI tool for sending Telegram notifications
│       └── main.py                    # Application entrypoint (wires everything)
├── cognitive/
│   ├── GEMINI.md                      # System persona & operational directives
│   ├── SOUL.md                        # Core identity companion specification
│   ├── MEMORY.example.md              # Persistent memory structure template
│   └── ARCHITECTURE.md               # Deep-dive architectural specification
└── skills/                            # Open Agent Skills library
    ├── agy-cli/                       # Orchestration & CLI flags guide
    ├── agy-create-project/            # Scaffolding verified repositories
    ├── find-skills/                   # Discovering open skills
    ├── github-agy-auditor/            # Automated code and repo audits
    ├── merge-reconciler/              # Systematic Git merge conflict resolution
    ├── ml-research-architect/         # Frontier Deep Learning research framework
    ├── plan/                          # Architectural implementation planning
    ├── requesting-code-review/        # Pre-commit sanity & secret inspection
    ├── simplify-code/                 # Code refactoring & complexity reduction
    ├── systematic-debugging/          # 4-phase bug elimination methodology
    ├── telegram-formatting/           # Mobile & Telegram formatting rules
    └── test-driven-development/       # Red-Green-Refactor TDD cycle
```

---

## Module Overview

| Module | Responsibility |
|---|---|
| `constants.py` | All tunable values — timeouts, limits, paths, and AGY flags |
| `messages.py` | All user-facing strings — the single source of truth for every message |
| `config.py` | JSON config and state loading, authorization check |
| `utils.py` | Message chunking, chunked Telegram replies, typing indicator |
| `stt.py` | Lazy-loaded `faster-whisper` model, transcription, status queries |
| `executor.py` | AGY subprocess execution, stream-json parsing, step tracking |
| `handlers.py` | Telegram command and message handlers (`BotHandlers` class) |
| `notifier.py` | Standalone CLI for sending messages from cron jobs and scripts |
| `main.py` | Wires all modules, configures logging, starts the bot |

---

## Installation & Setup

### 1. Prerequisites
- **Operating System:** Linux (Debian, Ubuntu, Arch, Fedora)
- **Python:** Python 3.10 or higher
- **Antigravity CLI:** Google Antigravity CLI (`agy`) installed and authenticated
- **Audio Processing:** `ffmpeg` (required for Telegram audio decoding)
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

### 2. Clone and Run Setup Script
```bash
git clone https://github.com/PilotLeoYan/jarvis-antigravity-agent.git
cd jarvis-antigravity-agent

# Run automated setup (creates venv, installs deps, links skills)
chmod +x setup.sh
./setup.sh
```

### 3. Telegram Bot Configuration
1. Open Telegram and talk to [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, choose a name and a username (e.g., `my_jarvis_bot`).
3. Copy the HTTP API token generated.
4. Retrieve your Telegram User ID (e.g., using [@userinfobot](https://t.me/userinfobot)).
5. Copy and edit the config file:
```bash
cp config.example.json config.json
```
```json
{
  "bot_token": "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ",
  "allowed_users": [987654321],
  "default_chat_id": 987654321,
  "working_directory": "/home/youruser",
  "agy_path": "agy",
  "default_flags": [
    "--dangerously-skip-permissions"
  ]
}
```

> The config file location can be overridden with the `AGY_TELEGRAM_CONFIG` environment variable. The bot token can also be provided via `TELEGRAM_BOT_TOKEN`.

### 4. Running the Bot

#### Manual Execution (Foreground)
```bash
jarvis-antigravity-agent
```
Or directly via Python:
```bash
python -m jarvis_antigravity_agent
```

#### Running as a Daemon (`systemd` User Service)
To ensure the assistant starts automatically on boot and recovers from system interruptions:
```bash
# Copy service unit to systemd user directory
mkdir -p ~/.config/systemd/user
cp systemd/agy-telegram.service ~/.config/systemd/user/

# Reload and start service
systemctl --user daemon-reload
systemctl --user enable --now agy-telegram.service

# Check status and live logs
systemctl --user status agy-telegram.service
journalctl --user -u agy-telegram.service -f
```

---

## Bot Commands & Usage

| Command | Aliases | Description |
|---|---|---|
| `/help` | `/ayuda`, `/start` | Displays available commands and quick-start guide. |
| `/new` | `/nuevo` | Resets conversation context; next prompt starts clean. |
| `/status` | `/estado` | Displays AGY engine state, CPU load, STT status, and disk usage. |
| `/cancel` | `/cancelar` | Terminates any active running task immediately. |

### Sending Voice Notes
Send voice notes or audio files directly to the bot. The integrated `faster-whisper` engine transcribes speech locally and feeds the transcription to `agy`, streaming execution progress back into the chat.

### Sending Alerts from Shell Scripts / Cron Jobs
Use the `jarvis-send-message` CLI tool to deliver automated reports, pipeline notifications, or alerts directly to your Telegram chat:
```bash
# Pass message as argument
jarvis-send-message "Backup completed successfully."

# Pipe output from terminal command
df -h | jarvis-send-message

# Target a specific chat ID
jarvis-send-message --chat-id 987654321 "Deployment finished."
```

---

## Cognitive Engine & Guidelines

The agent's personality and behavioral boundaries are governed by `cognitive/GEMINI.md`:
- **Socratic & Critical:** Avoids superficial affirmations; rigorously tests engineering hypotheses.
- **Mobile-First Telegram Formatting:**
  - **NO Markdown `#` Headings:** Telegram renders headers as literal `#` text; bold text prefixed with descriptive emojis is enforced instead.
  - **No LaTeX or Tables:** Formats mathematical derivations and data cleanly using code blocks and lists to prevent mobile rendering artifacts.
  - **Rich Emojis:** Employs functional emojis for instant visual hierarchy.

---

## Configuration Reference

All tunable parameters live in `constants.py`. The table below lists the most important ones:

| Constant | Default | Description |
|---|---|---|
| `MAX_MESSAGE_LENGTH` | `4000` | Maximum Telegram message length before splitting |
| `AGY_PROCESS_TIMEOUT` | `360.0` s | Time before forcefully killing an AGY process |
| `EDIT_THROTTLE_SECONDS` | `1.2` s | Minimum interval between status message edits |
| `MAX_STATUS_ITEMS` | `12` | Max step items shown during execution |
| `MAX_COMPLETED_ITEMS` | `15` | Max step items shown on completion |
| `WHISPER_MODEL_SIZE` | `"base"` | Whisper model variant |
| `WHISPER_COMPUTE_TYPE` | `"int8"` | Quantization type for CPU inference |
| `AGY_DEFAULT_FLAGS` | `["--dangerously-skip-permissions"]` | Default flags passed to `agy` |

---

## Security & Privacy
- **Strict User Whitelisting:** Only Telegram user IDs configured in `allowed_users` can interact with the bot. Unauthorized requests are dropped.
- **Local Audio Processing:** Voice notes are transcribed directly on your CPU without transmitting audio to cloud APIs.
- **Git Security Policy:** `.gitignore` strictly excludes tokens, `.pem` certificates, private keys, and runtime databases.

---

## License
This project is licensed under the [MIT License](LICENSE).
