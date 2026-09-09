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
command -v agy >/dev/null 2>&1 || { echo >&2 "[*] Note: Google Antigravity CLI ('agy') not found in PATH. Ensure it is installed in ~/.local/bin or specify its absolute path in config.yaml."; }

# 2. Install package with uv (preferred) or fallback to pip venv
if command -v uv >/dev/null 2>&1; then
    echo "[+] Installing package with uv..."
    uv sync
    echo "[+] Package installed. Entrypoints available: jarvis-antigravity-agent, jarvis-send-message, jarvis-spawn-agent, jarvis-mcp, jarvis-update, jarvis-uninstall"
else
    echo "[+] uv not found — falling back to pip venv..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -e .
fi

# 3. Configuration Scaffolding
if [ ! -f "config.yaml" ] && [ ! -f "config.yml" ] && [ ! -f "config.json" ]; then
    echo "[+] Creating config.yaml from template..."
    cp config.example.yaml config.yaml
    echo "[*] Remember to edit config.yaml with your Telegram Bot Token and User ID."
else
    echo "[+] Configuration file already exists."
fi

# 4. Cognitive Setup
AGENT_CONFIG_DIR="$HOME/.gemini/config"
mkdir -p "$AGENT_CONFIG_DIR"
if [ ! -f "$AGENT_CONFIG_DIR/SOUL.md" ]; then
    echo "[+] Deploying cognitive rules to $AGENT_CONFIG_DIR/SOUL.md..."
    cp cognitive/SOUL.md "$AGENT_CONFIG_DIR/SOUL.md"
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
            echo "    Linked skill: $sname"
        fi
    fi
done

# 6. Binary Symlinks Linking to ~/.local/bin
USER_BIN_DIR="$HOME/.local/bin"
mkdir -p "$USER_BIN_DIR"
VENV_BIN_DIR="$SCRIPT_DIR/.venv/bin"
if [ ! -d "$VENV_BIN_DIR" ]; then
    VENV_BIN_DIR="$SCRIPT_DIR/venv/bin"
fi

ENTRYPOINTS=(
    "jarvis-antigravity-agent"
    "jarvis-send-message"
    "jarvis-spawn-agent"
    "jarvis-mcp"
    "jarvis-update"
    "jarvis-uninstall"
)

echo "[+] Linking executable entrypoints into $USER_BIN_DIR..."
for ep in "${ENTRYPOINTS[@]}"; do
    if [ -f "$VENV_BIN_DIR/$ep" ]; then
        ln -sf "$VENV_BIN_DIR/$ep" "$USER_BIN_DIR/$ep"
        chmod +x "$USER_BIN_DIR/$ep" 2>/dev/null || true
        echo "    Linked binary: $ep -> $USER_BIN_DIR/$ep"
    fi
done

# 7. Systemd Service Deployment
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
if [ -f "$SCRIPT_DIR/systemd/agy-telegram.service" ]; then
    echo "[+] Deploying systemd user service template to $SYSTEMD_USER_DIR/agy-telegram.service..."
    cp "$SCRIPT_DIR/systemd/agy-telegram.service" "$SYSTEMD_USER_DIR/agy-telegram.service"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload 2>/dev/null || true
    fi
fi

echo ""
echo "=========================================================="
echo "   Setup Complete!"
if [[ ":$PATH:" != *":$USER_BIN_DIR:"* ]]; then
    echo ""
    echo "   [*] Note: $USER_BIN_DIR is not currently in your PATH."
    echo "       To run commands directly, add it to your shell profile:"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo ""
echo "   To start manually:"
echo "     jarvis-antigravity-agent"
echo ""
echo "   To enable and start as a systemd user daemon:"
echo "     systemctl --user enable --now agy-telegram.service"
echo ""
echo "   To view service logs:"
echo "     journalctl --user -u agy-telegram.service -f"
echo "=========================================================="
