#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   Jarvis Antigravity Agent - Automated Environment Setup"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Dependency Checks
echo "[+] Checking system prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo >&2 "[-] Error: python3 is required. Aborting."; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo >&2 "[-] Warning: ffmpeg is not installed. Voice note processing requires ffmpeg (sudo apt install ffmpeg)."; }
command -v agy >/dev/null 2>&1 || { echo >&2 "[*] Note: Google Antigravity CLI ('agy') not found in PATH. Ensure it is installed in ~/.local/bin or specify its absolute path in config.json."; }

# 2. Virtual Environment
if [ ! -d "venv" ]; then
    echo "[+] Creating Python virtual environment (venv)..."
    python3 -m venv venv
else
    echo "[+] Virtual environment already exists."
fi

echo "[+] Installing dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 3. Configuration Scaffolding
if [ ! -f "bridge/config.json" ]; then
    echo "[+] Creating bridge/config.json from template..."
    cp bridge/config.example.json bridge/config.json
    echo "[*] Remember to edit bridge/config.json with your Telegram Bot Token and User ID."
else
    echo "[+] Configuration file bridge/config.json exists."
fi

# 4. Cognitive Setup
AGENT_CONFIG_DIR="$HOME/.gemini/config"
mkdir -p "$AGENT_CONFIG_DIR"
if [ ! -f "$AGENT_CONFIG_DIR/GEMINI.md" ]; then
    echo "[+] Deploying cognitive rules to $AGENT_CONFIG_DIR/GEMINI.md..."
    cp cognitive/GEMINI.md "$AGENT_CONFIG_DIR/GEMINI.md"
fi

# 5. Skills Linking
AGENT_SKILLS_DIR="$HOME/.agents/skills"
mkdir -p "$AGENT_SKILLS_DIR"
echo "[+] Linking generic skills into $AGENT_SKILLS_DIR..."
for skill in skills/*; do
    if [ -d "$skill" ]; then
        sname=$(basename "$skill")
        target="$AGENT_SKILLS_DIR/$sname"
        if [ ! -e "$target" ]; then
            ln -s "$SCRIPT_DIR/$skill" "$target"
            echo "    -> Linked skill: $sname"
        fi
    fi
done

echo ""
echo "=========================================================="
echo "   Setup Complete!"
echo "   To start manually:"
echo "     ./venv/bin/python bridge/bot.py"
echo ""
echo "   To install as a systemd user daemon:"
echo "     mkdir -p ~/.config/systemd/user"
echo "     cp systemd/agy-telegram.service ~/.config/systemd/user/"
echo "     systemctl --user daemon-reload"
echo "     systemctl --user enable --now agy-telegram.service"
echo "=========================================================="
