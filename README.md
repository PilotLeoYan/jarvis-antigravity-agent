> [!CAUTION]
> **IMPORTANT COMPLIANCE & RESEARCH NOTICE**
>
> This project was developed strictly as an educational and architectural exploration of event-driven agent IPC, streaming output processing, and headless developer tooling.
>
> **Terms of Service Considerations:**
> In accordance with Section 108 of the [Google Antigravity Additional Terms of Service](https://antigravity.google/terms) and official policies clarified in [Gemini CLI Discussion #20632](https://github.com/google-gemini/gemini-cli/discussions/20632), connecting third-party bridges or unofficial daemon harnesses to consumer-subsidized Antigravity/Gemini CLI OAuth tokens is strictly restricted and subject to automated abuse enforcement (Two-Strike account suspension policy).
>
> + **Production Recommendation:** For production bots, continuous automations, or third-party integrations, users should decouple from consumer CLI sessions and exclusively employ official metered endpoints such as **Google AI Studio (Gemini API Keys)** or **Google Cloud Vertex AI**, which explicitly permit automated client access.
> + The author assumes no responsibility for account suspensions resulting from deployment on non-metered personal accounts.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)](https://core.telegram.org/bots)
[![Speech-to-Text](https://img.shields.io/badge/STT-faster--whisper%20(int8)-orange)](https://github.com/SYSTRAN/faster-whisper)
[![Engine](https://img.shields.io/badge/Core-Google%20Antigravity%20CLI-purple)]()

<img align="left" src="assets/jarvis-icon.png" width="175" style="margin-right: 10px;">

<ul id="user-content-toc"><summary><h1>Antigravity Agent 😸+🕷️</h1></summary></ul>

A simple Hermes-Agent copy using **Google Antigravity CLI**<br>
as main engine.

<br>⭐️ **Why did I do this project?** Inspired by Peter Parker’s autonomous assistant in Spider-Man 🕷️, I wanted to explore the systems engineering behind building an always-available, local-first agent bridge combining speech recognition, headless CLI interaction, and Linux system services.

**Some features**:

+ 💬 Use of Telegram
+ 🗣️ Local speech-to-text
+ 🧠 Power of AGY

## ✅️ Prerequisites

- **Linux OS** (Ubuntu 22.04+ or Debian-based distribution recommended)
- **Python 3.10+**
- **uv** package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Google Antigravity CLI (`agy`):** installed and authenticated in `~/.local/bin` or available in `PATH`. [Install here](https://antigravity.google/product/antigravity-cli)
- **ffmpeg** (required for processing Telegram voice notes): `sudo apt install ffmpeg`

## ⤵️ Installation

Clone the repository and run the automated setup script:

```bash
git clone https://github.com/PilotLeoYan/jarvis-antigravity-agent.git
cd jarvis-antigravity-agent
chmod +x setup.sh
./setup.sh
```

## ⚙️ Configuration

Copy the example configuration file:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` to specify:

+ Telegram Bot token: `bot_token: "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"`
+ Authorized users IDs: `allowed_users: - 123456789`
+ Working directory: `working_dir: "/home/username"`

## 🔄 Running as a Systemd Service

When using the automated installer (`./setup.sh`), the service file is automatically copied to `~/.config/systemd/user/agy-telegram.service` and the required entrypoint binaries are linked into `~/.local/bin/`.

To enable and run Jarvis continuously as a background daemon:

```bash
systemctl --user enable --now agy-telegram.service
```

To reload and start the service on your system:
```bash
systemctl --user daemon-reload
systemctl --user restart agy-telegram.service
systemctl --user status agy-telegram.service
```

Inspect service logs with:

```bash
journalctl --user -u agy-telegram.service -f
```

## 🚮 Uninstallation & Cleanup

To stop the background daemon and safely uninstall the agent:

```bash
./uninstall.sh
```

- `--purge-personal`: Removes personal configuration files (`config.yaml`), `state.json`, credentials, and voice caches.
- `--purge-agy`: Removes Google Antigravity application data (`~/.gemini`, `~/.agents`, `~/.config/Antigravity`).
- `--all`: Completely removes the systemd daemon, personal files, and all AGY data.
- `--dry-run`: Simulates the uninstallation without making any filesystem or daemon changes.
- `-y`, `--yes`: Non-interactive mode (proceed without confirmation prompts).

## 🎟️ Contribution

I’m just a student who undertook this project because I’ve got a lot on my plate; any [☉ Issues](https://github.com/PilotLeoYan/jarvis-antigravity-agent/issues) or [🔃 PRs](https://github.com/PilotLeoYan/jarvis-antigravity-agent/pulls) are welcome.

<a href="https://www.star-history.com/?repos=pilotleoyan%2Fjarvis-antigravity-agent&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=pilotleoyan/jarvis-antigravity-agent&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=pilotleoyan/jarvis-antigravity-agent&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=pilotleoyan/jarvis-antigravity-agent&type=timeline&legend=top-left" />
 </picture>
</a>
